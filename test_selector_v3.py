import os, time, traceback
from crawler import WebDriverManager
from parser import PostParser
from selenium.webdriver.common.by import By
import re
import shutil
from pathlib import Path

URL = "https://guba.eastmoney.com/list,000333,1.html"
headless = False

print("启动 WebDriver（headless=%s）..." % headless)
wdm = WebDriverManager(headless=headless)
driver, profile = wdm.create_driver()
try:
    print("打开页面：", URL)
    driver.get(URL)
    time.sleep(2)
    # 新的 selector
    sel = "div.table_list tr"
    els = driver.find_elements("css selector", sel)
    print("selector:", sel)
    print("匹配到 tr 的数量:", len(els))
    # 打印前 5 个 tr 的 outerHTML（截断）
    for i, el in enumerate(els[:6]):
        print(f"---- tr #{i} outerHTML (first 1000 chars) ----")
        print(el.get_attribute("outerHTML")[:1000].replace("\n"," "))
    # 找到第一个真正的数据行（至少 4 个 td）
    data_rows = [e for e in els if len(e.find_elements("css selector", "td")) >= 4]
    print("符合 data 行条件的数量:", len(data_rows))
    if data_rows:
        parser = PostParser()
        try:
            doc = parser.parse_post_info(data_rows[0])
            print("parse_post_info 输出样例:")
            print(doc)
        except Exception:
            print("解析时抛出异常：")
            traceback.print_exc()
    else:
        print("未找到符合数据条件的行，可能需要进一步检查 DOM。")
finally:
    print("退出 driver 并清理 profile")
    try:
        wdm.quit_driver()
    except Exception as e:
        print("quit_driver 异常：", e)

# 替换 parser.py 内的 parse_comment_num 函数为以下实现

@staticmethod
def parse_comment_num(html):
    num_element = html.find_element(By.CSS_SELECTOR, 'td:nth-child(2) > div')
    text = (num_element.text or "").strip()
    if not text:
        return 0

    # 直接是纯数字（例如 "1234"）
    cleaned = text.replace(',', '')  # 移除千位分隔符
    if cleaned.isdigit():
        return int(cleaned)

    # 常见格式：以 '万' 结尾（例如 "1.2万"）
    try:
        if cleaned.endswith('万'):
            num_part = cleaned[:-1].strip()
            return int(float(num_part.replace(',', '')) * 10000)
    except Exception:
        pass

    # 退路：从字符串中提取第一个数字（支持小数和千分号）
    m = re.search(r'(\d[\d,\.]*)', cleaned)
    if m:
        s = m.group(1).replace(',', '')
        try:
            if '.' in s:
                return int(float(s))
            return int(s)
        except Exception:
            pass

    # 无法解析则返回 0（避免抛异常）
    return 0

repo = Path(r"c:\Users\啊景\Desktop\EastMoney_Crawler-1.5.0")
crawler_path = repo / "crawler.py"
bak_path = repo / "crawler.py.bak5"

if not crawler_path.exists():
    print("找不到 crawler.py:", crawler_path)
    raise SystemExit(1)

# 备份
shutil.copy2(crawler_path, bak_path)
print("已备份到", bak_path)

text = crawler_path.read_text(encoding="utf-8")

old_line = 'posts = self.driver.find_elements("css selector", "div.table_list tr")'

new_block = '''posts = self.driver.find_elements("css selector", "div.table_list tr")
        # 过滤表头和非帖子行：保留 class 包含 "listitem" 的 tr，或第 3 列包含 a 链接的 tr
        try:
            filtered = []
            for p in posts:
                cls = (p.get_attribute("class") or "")
                if "listitem" in cls:
                    filtered.append(p)
                    continue
                # 第三列存在链接则视为帖子行
                if p.find_elements("css selector", "td:nth-child(3) a"):
                    filtered.append(p)
            posts = filtered
        except Exception:
            # 出错时保留原 posts（解析阶段会跳过异常）
            pass
'''

if old_line in text:
    new_text = text.replace(old_line, new_block)
    crawler_path.write_text(new_text, encoding="utf-8")
    print("已替换并写入 crawler.py（备份在 crawler.py.bak5）")
else:
    print("未找到要替换的旧行，请用手动方式在编辑器中替换。")
    # 为调试输出，打印文件中包含该关键字的上下文行数
    for i, line in enumerate(text.splitlines(), 1):
        if "table_list" in line or "articlelistnew" in line or "find_elements" in line:
            print(f"{i}: {line.strip()}")