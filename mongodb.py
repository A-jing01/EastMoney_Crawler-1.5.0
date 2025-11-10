from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError, PyMongoError
import datetime
import logging
import json, os

# 使用明确的 logger 名称，便于在 logging.conf 中单独控制
logger = logging.getLogger('eastmoney_crawler.mongodb')

class MongoAPI(object):

    def __init__(self, db_name: str, collection_name: str, host='localhost', port=27017, uri=None):
        """
        如果提供 uri，则优先使用 uri（支持认证或非默认端口）。
        调用签名与 crawler.py 的使用一致： MongoAPI("post_info", "post_000333")
        """
        self.host = host
        self.port = port
        self.db_name = db_name
        self.collection = collection_name

        try:
            if uri:
                self.client = MongoClient(uri, serverSelectionTimeoutMS=3000)
            else:
                self.client = MongoClient(host=self.host, port=self.port, serverSelectionTimeoutMS=3000)
            # 触发连接检测
            self.client.server_info()
        except Exception as e:
            raise RuntimeError(f"无法连接到 MongoDB ({uri or f'{self.host}:{self.port}'}): {e}")

        self.db = self.client[self.db_name]
        self.coll = self.db[self.collection]

    def insert_one(self, kv_dict):
        try:
            res = self.coll.insert_one(kv_dict)
            return res.inserted_id
        except PyMongoError:
            logger.exception("[MongoAPI] insert_one 错误")
            return None

    def insert_many(self, li_dict):
        """
        Insert many documents. Returns a summary dict:
        {'inserted_count': int, 'errors': int, 'error': optional str}
        """
        if not li_dict:
            return {'inserted_count': 0, 'errors': 0}

        try:
            res = self.coll.insert_many(li_dict, ordered=False)
            inserted = len(res.inserted_ids) if getattr(res, 'inserted_ids', None) is not None else 0
            return {'inserted_count': inserted, 'errors': 0}
        except BulkWriteError as bwe:
            det = getattr(bwe, 'details', {}) or {}
            try:
                inserted = det.get('nInserted', 0)
            except Exception:
                inserted = 0
            write_errors = det.get('writeErrors', []) if isinstance(det, dict) else []
            logger.exception("[MongoAPI] insert_many 部分失败")
            return {
                'inserted_count': inserted,
                'errors': len(write_errors),
                'error': str(bwe)
            }
        except PyMongoError as e:
            logger.exception("[MongoAPI] insert_many 错误")
            return {'inserted_count': 0, 'errors': 1, 'error': str(e)}

    def upsert_many(self, docs, id_field='_id', update_fields=None, insert_on_new=None):
        """
        批量 upsert（更安全的白名单策略）：
        - docs: 文档列表（每个为 dict）
        - id_field: 默认用于回退匹配的字段（当 post_url 不存在时）
        - update_fields: 可选列表，仅这些字段会被放入 $set（动态字段）
          默认: ['post_view', 'comment_num', 'last_crawled', 'post_time']
        - insert_on_new: 可选列表，首次插入时会把这些字段放入 $setOnInsert（静态元数据）
          默认: ['post_title', 'post_url', 'author', 'post_date', 'post_time']
        返回 summary dict（与之前一致），并在异常时包含 'error' 字段。
        """
        if not docs:
            return {'upserted_count': 0, 'matched_count': 0, 'modified_count': 0}

        # 默认白名单
        if update_fields is None:
            # 不把 'post_time' 放到 $set，避免与已存在不同类型冲突
            update_fields = ['post_view', 'comment_num', 'last_crawled']
        if insert_on_new is None:
            # 使用 parser 输出的字段名 'post_author'
            insert_on_new = ['post_title', 'post_url', 'post_author', 'post_date', 'post_time']

        ops = []
        for d in docs:
            post_url = d.get('post_url')
            if post_url:
                filt = {'post_url': post_url}
            else:
                if id_field in d:
                    filt = {id_field: d[id_field]}
                else:
                    logger.warning("[MongoAPI] upsert_many: skipping doc with no match key")
                    continue

            # 构建 $set（只包含白名单里的字段且不包含 _id）
            set_doc = {}
            for k in update_fields:
                if k == '_id':
                    continue
                if k == 'last_crawled':
                    # 始终更新/写入为当前 UTC datetime
                    set_doc['last_crawled'] = datetime.datetime.utcnow()
                elif k in d:
                    set_doc[k] = d[k]

            # 构建 $setOnInsert（仅在首次插入写入静态字段）
            set_on_insert = {}
            for k in insert_on_new:
                if k != '_id' and k in d:
                    set_on_insert[k] = d[k]

            update_op = {}
            if set_doc:
                update_op['$set'] = set_doc
            if set_on_insert:
                update_op['$setOnInsert'] = set_on_insert

            # 如果没有可写字段（既没动态字段也没静态字段），跳过
            if not update_op:
                logger.warning("[MongoAPI] upsert_many: no updatable fields for doc %s, skipped.", filt)
                continue

            ops.append(UpdateOne(filt, update_op, upsert=True))

        if not ops:
            return {'upserted_count': 0, 'matched_count': 0, 'modified_count': 0}

        try:
            res = self.coll.bulk_write(ops, ordered=False)
            return {
                'upserted_count': getattr(res, 'upserted_count', 0),
                'matched_count': getattr(res, 'matched_count', 0),
                'modified_count': getattr(res, 'modified_count', 0),
            }
        except BulkWriteError as bwe:
            det = getattr(bwe, 'details', {}) or {}
            logger.exception("[MongoAPI] upsert_many BulkWriteError: %s", det)
            try:
                # 写到仓库目录下的 tmp 文件，便于后续审查
                path = os.path.join(os.getcwd(), "bulk_write_error_details.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(det, f, default=str, ensure_ascii=False, indent=2)
                logger.error("bulk write details written to %s", path)
            except Exception:
                logger.exception("无法写 BulkWriteError details 到文件")
            try:
                upserted = det.get('nUpserted', det.get('upserted', 0)) or 0
            except Exception:
                upserted = 0
            try:
                matched = det.get('nMatched', 0) or 0
            except Exception:
                matched = 0
            try:
                modified = det.get('nModified', 0) or 0
            except Exception:
                modified = 0
            logger.exception("[MongoAPI] upsert_many BulkWriteError")
            return {
                'upserted_count': upserted,
                'matched_count': matched,
                'modified_count': modified,
                'error': str(bwe),
            }
        except Exception as e:
            logger.exception("[MongoAPI] upsert_many 错误")
            return {
                'upserted_count': 0,
                'matched_count': 0,
                'modified_count': 0,
                'error': str(e),
            }

    def find_one(self, query1=None, query2=None):
        try:
            return self.coll.find_one(filter=(query1 or {}), projection=(query2 or None))
        except PyMongoError:
            logger.exception("[MongoAPI] find_one 错误")
            return None

    def find(self, query1=None, query2=None):
        try:
            cursor = self.coll.find(filter=(query1 or {}), projection=(query2 or None))
            return list(cursor)
        except PyMongoError:
            logger.exception("[MongoAPI] find 错误")
            return []

    def find_first(self):
        try:
            return self.coll.find_one(sort=[('_id', 1)])
        except PyMongoError:
            logger.exception("[MongoAPI] find_first 错误")
            return None

    def find_last(self):
        try:
            return self.coll.find_one(sort=[('_id', -1)])
        except PyMongoError:
            logger.exception("[MongoAPI] find_last 错误")
            return None

    def count_documents(self):
        try:
            return self.coll.count_documents({})
        except PyMongoError:
            logger.exception("[MongoAPI] count_documents 错误")
            return 0

    def update_one(self, kv_dict):
        if '_id' not in kv_dict:
            logger.warning("[MongoAPI] update_one 需要包含 '_id' 字段")
            return None
        _id = kv_dict['_id']
        data = dict(kv_dict)
        data.pop('_id', None)
        try:
            res = self.coll.update_one({'_id': _id}, {'$set': data}, upsert=False)
            return res.modified_count
        except PyMongoError:
            logger.exception("[MongoAPI] update_one 错误")
            return None

    def drop(self):
        try:
            self.coll.drop()
            return True
        except PyMongoError:
            logger.exception("[MongoAPI] drop 错误")
            return False
