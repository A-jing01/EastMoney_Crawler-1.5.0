# 用途：备份 post_000333 -> 去重（按 date/time/latest _id 保留）-> 创建 post_url 唯一索引
# 运行：python .\dedupe_and_create_index_post_000333.py
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
import sys

COL = "post_000333"
DB = "post_info"

def backup_collection(db, src_name):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_name = f"{src_name}_backup_{ts}"
    print(f"[1/4] 备份集合 {src_name} -> {bak_name} ...")
    count = 0
    src = db[src_name]
    bak = db[bak_name]
    docs = list(src.find({}))
    if docs:
        bak.insert_many(docs)
        count = bak.count_documents({})
    print(f"  备份完成，备份集合 {bak_name} 文档数: {count}")
    return bak_name

def parse_dt(d, t):
    try:
        if d and t:
            return datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
        if d:
            return datetime.strptime(d, "%Y-%m-%d")
    except Exception:
        pass
    return None

def find_duplicate_groups(coll):
    pipeline = [
        {"$match": {"post_url": {"$exists": True, "$ne": ""}}},
        {"$group": {"_id": "$post_url", "ids": {"$push": {"_id": "$_id", "post_date": "$post_date", "post_time": "$post_time"}}}},
        {"$project": {"_id": 1, "count": {"$size": "$ids"}, "ids": 1}},
        {"$match": {"count": {"$gt": 1}}}
    ]
    return list(coll.aggregate(pipeline, allowDiskUse=True))

def choose_keep_id(doc_list):
    def key_fn(item):
        dt = parse_dt(item.get("post_date"), item.get("post_time"))
        if dt:
            return dt
        oid = item.get("_id")
        if isinstance(oid, ObjectId):
            return oid.generation_time
        return datetime.min
    sorted_list = sorted(doc_list, key=key_fn, reverse=True)
    return sorted_list[0]["_id"], [d["_id"] for d in sorted_list[1:]]

def chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i+size]

def dedupe_collection(coll, dry_run=False):
    print("[2/4] 扫描重复 post_url ...")
    groups = find_duplicate_groups(coll)
    print(f"  找到 {len(groups)} 个重复 URL 组（每组 >1 条）")
    to_delete = []
    total_keep = 0
    for g in groups:
        ids = g.get("ids", [])
        if len(ids) <= 1:
            total_keep += len(ids)
            continue
        keep_id, del_ids = choose_keep_id(ids)
        total_keep += 1
        to_delete.extend(del_ids)
    print(f"  总计将要删除的文档数: {len(to_delete)} (保留每组一条，共保留 {total_keep} 条)")
    if dry_run:
        print("  dry_run=True，未执行删除。")
        return len(to_delete)
    BATCH = 500
    deleted_total = 0
    print("[3/4] 开始分批删除重复文档 ...")
    for batch in chunked(to_delete, BATCH):
        res = coll.delete_many({"_id": {"$in": batch}})
        deleted_total += res.deleted_count
        print(f"    已删除 {deleted_total} / {len(to_delete)}")
    print(f"  删除完成，总共删除: {deleted_total}")
    return deleted_total

def create_unique_index(coll):
    print("[4/4] 创建唯一索引 post_url ...")
    try:
        coll.create_index("post_url", unique=True)
        print("  唯一索引创建成功：post_url")
        return True
    except Exception as e:
        print("  创建索引失败：", e)
        return False

def main(dry_run=False):
    client = MongoClient("localhost", 27017)
    db = client[DB]
    coll = db[COL]

    # 1) 备份
    bak_name = backup_collection(db, COL)

    # 2) 去重（默认执行删除，除非 dry_run True）
    deleted = dedupe_collection(coll, dry_run=dry_run)

    # 3) 再检查是否还有重复
    remaining_dups = find_duplicate_groups(coll)
    if remaining_dups:
        print(f"注意：仍有 {len(remaining_dups)} 个重复组，无法创建唯一索引。请检查或手动处理。")
        return

    # 4) 创建唯一索引
    ok = create_unique_index(coll)
    if ok:
        print("流程完成：已备份 -> 去重 -> 创建唯一索引。")
    else:
        print("流程部分完成：备份并去重完成，但创建索引失败，请查看错误信息。")

if __name__ == "__main__":
    dry = "--dry-run" in sys.argv or "-n" in sys.argv
    main(dry_run=dry)
