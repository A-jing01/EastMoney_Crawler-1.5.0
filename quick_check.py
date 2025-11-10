from pymongo import MongoClient, errors
import pprint

def check_mongo(host='localhost', port=27017, timeout_ms=3000):
    try:
        client = MongoClient(host=host, port=port, serverSelectionTimeoutMS=timeout_ms)
        # 触发连接检测
        info = client.server_info()
        print("MongoDB 连接成功，版本:", info.get("version"))
    except errors.ServerSelectionTimeoutError as e:
        print("无法连接到 MongoDB:", e)
        return

    # 列出数据库与集合样例
    dbs = client.list_database_names()
    print("数据库列表:", dbs)

    for db_name in ('post_info', 'comment_info'):
        if db_name in dbs:
            db = client[db_name]
            cols = db.list_collection_names()
            print(f"\n数据库 {db_name} 存在，集合：{cols}")
            # 显示每个集合的文档数和一条示例
            for col in cols:
                coll = db[col]
                cnt = coll.count_documents({})
                sample = coll.find_one()
                print(f"  集合 {col} - 文档数: {cnt}")
                print("  示例文档:")
                pprint.pprint(sample, indent=4)
        else:
            print(f"\n数据库 {db_name} 不存在或为空")

# 测试插入示例（直接运行）
from pymongo import MongoClient
client = MongoClient("localhost", 27017)
db = client['post_info']
col = db['post_test']
res = col.insert_one({"test": "ok", "time": __import__('time').time()})
print("inserted_id:", res.inserted_id)
print("count in post_test:", col.count_documents({}))

if __name__ == "__main__":
    # 根据需要修改 host/port
    check_mongo(host='localhost', port=27017)