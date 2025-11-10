from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError, PyMongoError
import datetime
import logging

# 使用明确的 logger 名称，便于在 logging.conf 中单独控制
logger = logging.getLogger('eastmoney_crawler.mongodb')

class MongoAPI:
    def __init__(self, uri, db_name, collection_name):
        """
        简单的 MongoAPI helper（用于演示/补丁应用场景）
        """
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

    def insert_one(self, document):
        try:
            result = self.collection.insert_one(document)
            return result.inserted_id
        except PyMongoError:
            logger.exception("[MongoAPI] insert_one 错误")
            return None

    def insert_many(self, documents):
        """
        Insert many documents, 返回一个 summary dict。
        """
        if not documents:
            return {'inserted_count': 0, 'errors': 0, 'error': None}

        try:
            result = self.collection.insert_many(documents, ordered=False)
            inserted = len(getattr(result, 'inserted_ids', []) or [])
            return {'inserted_count': inserted, 'errors': 0, 'error': None}
        except BulkWriteError as bwe:
            det = getattr(bwe, 'details', {}) or {}
            inserted = det.get('nInserted', 0) or 0
            write_errors = det.get('writeErrors', []) if isinstance(det, dict) else []
            logger.exception("[MongoAPI] insert_many 部分失败")
            return {
                'inserted_count': inserted,
                'errors': len(write_errors),
                'error': str(bwe)
            }
        except PyMongoError:
            logger.exception("[MongoAPI] insert_many 错误")
            return {'inserted_count': 0, 'errors': 1, 'error': 'PyMongoError'}

    def upsert_many(self, documents, identifier):
        """
        根据唯一键批量更新或插入文档。
        - identifier 可以是字符串（单键）或可迭代的键名列表（复合键）。
        - 使用 $set 更新（不覆盖 _id），并为每条记录写入 last_crawled (UTC datetime)。
        - 返回 summary dict，发生异常时包含 'error' 字段。
        """
        if not documents:
            return {
                'upserted_count': 0,
                'matched_count': 0,
                'modified_count': 0,
                'error': None,
            }

        bulk_ops = []
        for doc in documents:
            # 构建匹配键
            if isinstance(identifier, str):
                if identifier not in doc:
                    logger.warning("[MongoAPI] upsert_many 跳过文档：缺少标识字段 '%s'", identifier)
                    continue
                key = {identifier: doc[identifier]}
            else:
                # identifier 当作可迭代的键集合
                key = {}
                for k in identifier:
                    if k in doc:
                        key[k] = doc[k]
                if not key:
                    logger.warning("[MongoAPI] upsert_many 跳过文档：缺少复合标识字段 %s", identifier)
                    continue

            # 准备更新文档（不包含 _id）
            update_doc = {k: v for k, v in doc.items() if k != '_id'}
            update_doc['last_crawled'] = datetime.datetime.utcnow()
            bulk_ops.append(UpdateOne(key, {'$set': update_doc}, upsert=True))

        if not bulk_ops:
            return {
                'upserted_count': 0,
                'matched_count': 0,
                'modified_count': 0,
                'error': None,
            }

        try:
            result = self.collection.bulk_write(bulk_ops, ordered=False)
            # 从 result 安全读取计数
            upserted = getattr(result, 'upserted_count', None)
            if upserted is None:
                upserted = len(getattr(result, 'upserted_ids', {}) or {})
            matched = getattr(result, 'matched_count', 0)
            modified = getattr(result, 'modified_count', 0)
            return {
                'upserted_count': upserted,
                'matched_count': matched,
                'modified_count': modified,
                'error': None,
            }
        except BulkWriteError as bwe:
            det = getattr(bwe, 'details', {}) or {}
            upserted = det.get('nUpserted', det.get('upserted', 0)) or 0
            matched = det.get('nMatched', 0) or 0
            modified = det.get('nModified', 0) or 0
            logger.exception("[MongoAPI] upsert_many BulkWriteError")
            return {
                'upserted_count': upserted,
                'matched_count': matched,
                'modified_count': modified,
                'error': str(bwe),
            }
        except PyMongoError:
            logger.exception("[MongoAPI] upsert_many PyMongoError")
            return {
                'upserted_count': 0,
                'matched_count': 0,
                'modified_count': 0,
                'error': 'PyMongoError',
            }
        except Exception:
            logger.exception("[MongoAPI] upsert_many 未知错误")
            return {
                'upserted_count': 0,
                'matched_count': 0,
                'modified_count': 0,
                'error': 'unknown',
            }