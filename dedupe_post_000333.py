from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
import pprint

client = MongoClient("localhost", 27017)
db = client["post_info"]
coll = db["post_000333"]

# 聚合获取每个 post_url 的所有 _id 与 date/time
pipeline = [
    {"$match": {"post_url": {"$exists": True, "$ne": ""}}},
    {"$group": {"_id": "$post_url", "docs": {"$push": {"_id": "$_id", "post_date": "$post_date", "post_time": "$post_time"}}}}
]

to_delete = []
kept = 0
groups = list(coll.aggregate(pipeline, allowDiskUse=True))
print("Distinct URLs with docs:", len(groups))

def parse_dt(d, t):
    try:
        if d and t:
            return datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
        if d:
            return datetime.strptime(d, "%Y-%m-%d")
    except Exception:
        pass
    return None

for g in groups:
    docs = g.get("docs", [])
    if len(docs) <= 1:
        kept += len(docs)
        continue
    # 为每 doc 计算优先级：先按 date/time（越新越好），再按 ObjectId 时间
    def key_fn(item):
        dt = parse_dt(item.get("post_date"), item.get("post_time"))
        if dt:
            return (dt, None)
        # fallback to ObjectId generation time if available
        oid = item.get("_id")
        if isinstance(oid, ObjectId):
            return (oid.generation_time, None)
        return (datetime.min, None)
    docs_sorted = sorted(docs, key=key_fn, reverse=True)
    keep_id = docs_sorted[0]["_id"]
    kept += 1
    del_ids = [d["_id"] for d in docs_sorted[1:]]
    to_delete.extend(del_ids)

print("Total docs to delete:", len(to_delete))
# 删除（批量，分块）
BATCH = 500
deleted_total = 0
for i in range(0, len(to_delete), BATCH):
    batch = to_delete[i:i+BATCH]
    res = coll.delete_many({"_id": {"$in": batch}})
    deleted_total += res.deleted_count
    print(f"Deleted batch {i//BATCH + 1}: {res.deleted_count}")

print("Deleted total:", deleted_total)
print("Kept (with url):", kept)
print("Remaining total documents in collection:", coll.count_documents({}))
print("Done")