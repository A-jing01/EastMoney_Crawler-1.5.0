from pymongo import MongoClient
c = MongoClient("localhost", 27017)
coll = c["post_info"]["post_000333"]
types = ["double","string","object","array","bool","int","null"]
print("总文档数:", coll.count_documents({}))
for t in types:
    cnt = coll.count_documents({"post_time": {"$type": t}})
    print(f"post_time type {t}: {cnt}")
# 也展示其它常见类型名称
extra_types = ["date","timestamp","regex","undefined"]
for t in extra_types:
    print(f"post_time type {t}: {coll.count_documents({'post_time': {'$type': t}})}")
