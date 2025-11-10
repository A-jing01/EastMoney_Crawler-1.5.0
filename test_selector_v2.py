import os, time, traceback
from crawler import WebDriverManager

URL = "https://guba.eastmoney.com/list,000333,1.html"
headless = False  # 开启浏览器方便观察，如需无头把它设为 True

def search_text(ctx, token, radius=120):
    idx = ctx.find(token)
    if idx == -1:
        return None
    start = max(0, idx - radius)
    end = min(len(ctx), idx + len(token) + radius)
    return ctx[start:end].replace("\n", " ").replace("\r", " ")

print("启动 WebDriver（headless=%s）..." % headless)
wdm = WebDriverManager(headless=headless)
driver, profile = wdm.create_driver()

try:
    print("打开页面：", URL)
    driver.get(URL)
    time.sleep(2.5)  # 等待加载
    page = driver.page_source
    print("页面长度：", len(page))
    # 打印前 8192 字符的片段（避免输出过长）
    print("=== page_source 前 8192 字符片段 ===")
    print(page[:8192].replace("\n"," "))
    print("=== end page fragment ===\n")

    tokens = [
        "articlelistnew", "articleh", "class=\"article\"", "class='article'",
        "guba.eastmoney.com", "article-list", "articleList", "listContainer",
        "article-item", "li", "ul", "table"
    ]
    print("搜索常见标识并打印上下文：")
    found_any = False
    for t in tokens:
        ctx = search_text(page, t)
        if ctx:
            found_any = True
            print(f"--- 找到标识 '{t}' 的上下文片段 ---")
            print(ctx[:500])
    if not found_any:
        print("未找到常见标识（上述 tokens），将尝试打印包含 'guba' 的所有链接片段。")

    # 尝试用常见 selectors 查找元素并打印数量与部分 outerHTML
    selectors = [
        "div#articlelistnew .articleh",
        "div.articleh",
        "div.article",
        "div.article-list .article-item",
        "ul#articlelist li",
        "div#main .articleh",
        "div#articlelist .articleh",
        "div.list .article-item",
        "tr", "table", "li"
    ]
    print("\n尝试常见 CSS 选择器：")
    any_match = False
    for sel in selectors:
        els = driver.find_elements("css selector", sel)
        print(f"selector='{sel}' -> count={len(els)}")
        if els and not any_match:
            any_match = True
            print(">>> 首个匹配元素 outerHTML（前 1200 字符）:")
            print(els[0].get_attribute("outerHTML")[:1200].replace("\n"," "))
    if not any_match:
        # 退而求其次：查找所有指向 guba 的链接
        links = driver.find_elements("css selector", "a[href*='guba.eastmoney.com']")
        print(f"\n未匹配 selectors，找到指向 guba 的链接数量: {len(links)}")
        for i, a in enumerate(links[:10]):
            href = a.get_attribute("href")
            text = a.text.strip()[:80]
            print(f" link #{i}: href={href} text={text}")

except Exception:
    traceback.print_exc()
finally:
    print("退出 driver 并清理 profile")
    try:
        wdm.quit_driver()
    except Exception as e:
        print("quit_driver 异常：", e)