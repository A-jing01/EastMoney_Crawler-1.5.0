from pymongo import MongoClient
from datetime import datetime

client = MongoClient("localhost", 27017)
db = client["post_info"]
src = db["post_000333"]
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
bak_name = f"post_000333_backup_{ts}"
print("Backing up collection to:", bak_name)
# 注意：若数据非常大，这一步会复制数据量相同的文档到新集合
db[bak_name].insert_many(list(src.find({})))
print("Backup done. Count:", db[bak_name].count_documents({}))