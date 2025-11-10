"""
quick_test.py
- 测试 Selenium（chromedriver + Chrome）是否能启动并打开页面
- 测试 MongoDB 是否可连接并能插入文档
"""

import os
import tempfile
import shutil
import time
import argparse
from pymongo import MongoClient, errors

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

def create_webdriver():
    # 尝试使用 webdriver-manager 先行获取 chromedriver
    driver_path = None
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        driver_path = ChromeDriverManager().install()
        print("[quick_test] 使用 webdriver-manager 下载到的 chromedriver:", driver_path)
    except Exception as e:
        print("[quick_test] webdriver-manager 未生效或无法下载:", str(e))

    # 环境变量覆盖或 fallback PATH
    if not driver_path:
        driver_path = os.environ.get("CHROME_DRIVER_PATH") or shutil.which("chromedriver")
        if driver_path:
            print("[quick_test] 使用备选 chromedriver:", driver_path)
        else:
            raise RuntimeError("无法找到 chromedriver，请设置 CHROME_DRIVER_PATH 或安装 chromedriver 到 PATH。")

    options = Options()
    # 可选无头模式
    if os.environ.get("HEADLESS", "") == "1":
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-blink-features=AutomationControlled")
    # 使用临时 user-data-dir 避免 profile 冲突
    tmp_profile = tempfile.mkdtemp(prefix="em_crawler_profile_")
    options.add_argument(f"--user-data-dir={tmp_profile}")

    # 指定 Chrome 二进制（若提供）
    chrome_bin = os.environ.get("CHROME_BINARY_PATH")
    if chrome_bin:
        options.binary_location = chrome_bin
        print("[quick_test] 指定 Chrome 可执行文件:", chrome_bin)

    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    # 等待几秒观察页面加载
    return driver, tmp_profile

def test_selenium():
    print("=== Selenium 测试 ===")
    try:
        driver, tmp_profile = create_webdriver()
        driver.get("https://www.baidu.com")
        time.sleep(1)
        title = driver.title
        print("[quick_test] 打开百度，页面标题：", title)
        driver.quit()
    except Exception as e:
        print("[quick_test] Selenium 测试失败：", e)
        return False
    finally:
        # 清理临时 profile
        try:
            shutil.rmtree(tmp_profile)
        except Exception:
            pass
    return True

def test_mongo(db_name="post_info", ephemeral=False):
    """Test MongoDB connectivity.

    If ephemeral=True, the inserted test document will be removed before returning.
    Returns (ok: bool, inserted_id or None)
    """
    print("=== MongoDB 测试 ===")
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=4000)
        info = client.server_info()
        print("[quick_test] MongoDB 连接成功，版本:", info.get("version"))
        db = client.get_database(db_name)
        col = db.get_collection("post_test")
        res = col.insert_one({"quick_test": True, "ts": time.time()})
        inserted_id = res.inserted_id
        print("[quick_test] 插入测试文档，inserted_id:", inserted_id)
        count = col.count_documents({})
        print("[quick_test] 当前 post_test 集合计数:", count)

        if ephemeral:
            try:
                col.delete_one({"_id": inserted_id})
                print("[quick_test] 已删除临时测试文档", inserted_id)
            except Exception as e:
                print("[quick_test] 删除临时测试文档失败:", e)

        return True, inserted_id
    except errors.ServerSelectionTimeoutError as e:
        print("[quick_test] 无法连接到 MongoDB:", e)
        return False, None
    except Exception as e:
        print("[quick_test] MongoDB 测试异常:", e)
        return False, None

def parse_args():
    p = argparse.ArgumentParser(description="Quick environment test for Selenium + MongoDB")
    p.add_argument("--ephemeral", action="store_true", help="Insert then delete the test document in MongoDB")
    p.add_argument("--db", default="post_info", help="MongoDB database name to use for the test")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    ok_selenium = test_selenium()
    ok_mongo, _ = test_mongo(db_name=args.db, ephemeral=args.ephemeral)
    print("=== 总结 ===")
    print("Selenium:", "OK" if ok_selenium else "FAIL")
    print("MongoDB :", "OK" if ok_mongo else "FAIL")
