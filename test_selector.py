import os, time, traceback
from crawler import WebDriverManager
from parser import PostParser

url = "https://guba.eastmoney.com/list,000333,1.html"

# 可通过环境变量控制 headless
headless = False

print("开启 WebDriver（headless=%s）..." % headless)
wdm = WebDriverManager(headless=headless)
driver, profile = wdm.create_driver()
try:
    print("打开页面：", url)
    driver.get(url)
    time.sleep(2)  # 等待页面加载
    sel = "div#articlelistnew .articleh"
    els = driver.find_elements("css selector", sel)
    print("选择器:", sel)
    print("匹配到的元素数量:", len(els))
    for i, el in enumerate(els[:3]):
        outer = el.get_attribute("outerHTML")
        print(f"---- element #{i} outerHTML (first 800 chars) ----")
        print(outer[:800].replace("\n"," "))
    if len(els) == 0:
        print("未匹配到元素，可能需要更新选择器或页面结构已变。")
    else:
        parser = PostParser()
        print("尝试解析第一个元素为文档（调用 parser.parse_post_info）...")
        try:
            doc = parser.parse_post_info(els[0])
            print("解析结果文档样例：")
            print(doc)
        except Exception as e:
            print("解析时抛出异常：")
            traceback.print_exc()
finally:
    print("退出 driver 并清理 profile")
    try:
        wdm.quit_driver()
    except Exception as e:
        print("quit_driver 异常：", e)