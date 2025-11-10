# 保存文件 show_post_000333.py（一次性在 VS Code 新建并粘贴下面内容）
import pymongo, pprint
c = pymongo.MongoClient()
db = c['post_info']
coll = db['post_000333']
print('count:', coll.count_documents({}))
pprint.pprint(list(coll.find().sort([('_id', -1)]).limit(5)))