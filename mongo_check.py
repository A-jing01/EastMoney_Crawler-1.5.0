from pymongo import MongoClient
import pprint
try:
    client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=3000)
    info = client.server_info()
    print("MongoDB 版本:", info.get("version"))
    db = client.get_database("post_info")
    cols = db.list_collection_names()
    print("post_info 集合列表:", cols)
    for c in cols:
        cnt = db[c].count_documents({})
        print(f"  集合 {c} - 文档数: {cnt}")
        sample = db[c].find_one()
        print("  示例：")
        pprint.pprint(sample)
except Exception as e:
    print("Mongo 访问异常：", e)
