# filepath: c:\Users\啊景\Desktop\EastMoney_Crawler-1.5.0\run_pages.py
import argparse
import time
import random
import json
import logging
from pathlib import Path

# 尝试按项目约定使用已有 logger
logger = logging.getLogger("run_pages")
logger.setLevel(logging.INFO)
if not logger.handlers:
    # 简单控制台输出（项目已有 logging.conf 会接管更细致的配置）
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(ch)

# 延迟区间（秒）
MIN_DELAY = 1.0
MAX_DELAY = 3.0

def save_state(path: Path, state: dict):
    path.write_text(json.dumps(state, ensure_ascii=False))

def load_state(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

def safe_quit_crawler(crawler):
    """尝试优雅关闭 crawler 的 webdriver；不保证所有实现都有这些属性，做多重保护。"""
    if crawler is None:
        return
    # 常见属性名尝试
    for attr in ('driver', 'webdriver', '_driver', 'browser'):
        try:
            d = getattr(crawler, attr, None)
            if d:
                try:
                    d.quit()
                except Exception:
                    pass
        except Exception:
            pass
    # 如果有 WebDriverManager 对象，尝试调用其 quit/stop 方法
    for mgr_attr in ('wdm', 'webdriver_manager', 'wd_manager'):
        try:
            mgr = getattr(crawler, mgr_attr, None)
            if mgr:
                if hasattr(mgr, 'quit_driver'):
                    try:
                        mgr.quit_driver()
                    except Exception:
                        pass
                elif hasattr(mgr, 'stop'):
                    try:
                        mgr.stop()
                    except Exception:
                        pass
        except Exception:
            pass

def main():
    parser = argparse.ArgumentParser(description="Run PostCrawler over page range (safe sequential run).")
    parser.add_argument("--symbol", default="000333", help="板块/股票代码，例如 000333")
    parser.add_argument("--start", type=int, default=1, help="起始页（包含）")
    parser.add_argument("--end", type=int, default=50, help="结束页（包含）")
    parser.add_argument("--headless", action="store_true", help="是否使用 headless 模式")
    parser.add_argument("--state-file", default="run_pages_state.json", help="保存进度的文件")
    parser.add_argument("--max-retries", type=int, default=2, help="每页失败后重试次数（不含首次尝试）")
    args = parser.parse_args()

    state_path = Path(args.state_file)
    state = load_state(state_path)
    last_done = state.get(args.symbol, 0)
    start_page = max(args.start, last_done + 1)

    logger.info("开始抓取 symbol=%s pages %d..%d (resume from %d). headless=%s",
                args.symbol, args.start, args.end, last_done, args.headless)

    # 运行 crawler
    try:
        from crawler import PostCrawler
    except Exception as e:
        logger.exception("无法导入 PostCrawler: %s", e)
        return

    # 初始 prev_total 通过一次临时连接获取（安全）
    prev_total = None
    try:
        tmp = PostCrawler(args.symbol, headless=args.headless)
        try:
            prev_total = tmp.mongo.count_documents()
        except Exception:
            prev_total = None
        safe_quit_crawler(tmp)
    except Exception:
        prev_total = None

    inserted_total = 0
    modified_total = 0
    errors = []

    for page in range(start_page, args.end + 1):
        logger.info("开始抓取 page %d ...", page)
        attempt = 0
        success = False
        while attempt <= args.max_retries and not success:
            attempt += 1
            crawler = None
            t0 = time.time()
            try:
                crawler = PostCrawler(args.symbol, headless=args.headless)
                # 单页抓取
                crawler.crawl_post_info(start_page=page, end_page=page)
                success = True
            except Exception as e:
                # 记录并决定是否重试
                logger.exception("[retry] page %d attempt %d 发生异常: %s", page, attempt, e)
                if attempt <= args.max_retries:
                    backoff = 1.0 * (2 ** (attempt - 1))
                    logger.info("page %d 将在 %.1fs 后重试 (attempt %d/%d)", page, backoff, attempt, args.max_retries + 1)
                    time.sleep(backoff)
                else:
                    logger.error("[PostCrawler %s] page %d 最终失败: %s", args.symbol, page, e)
                    errors.append({"page": page, "error": str(e)})
            finally:
                # 尝试关闭该次创建的 crawler，释放 chromedriver
                try:
                    safe_quit_crawler(crawler)
                except Exception:
                    pass

        # 每页结束后的固定短延迟，避免请求节奏太规律
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        logger.info("page %d 尝试完成（耗时 %.1fs, success=%s），睡眠 %.1fs", page, time.time() - t0, success, delay)
        time.sleep(delay)

        # 更新并记录 Mongo 总数，用于估算本页写入
        try:
            # 重新创建一个轻量 PostCrawler 仅用于 mongo 访问，或直接用一个 MongoAPI 实例
            # 这里直接导入 mongodb 并创建 MongoAPI 保证不启动 webdriver
            from mongodb import MongoAPI
            m = MongoAPI("post_info", f"post_{args.symbol}")
            cur_total = m.count_documents()
            if prev_total is not None:
                delta = cur_total - prev_total
                logger.info("Mongo 总量: %d (本页增量 %d)", cur_total, delta)
                inserted_total += max(delta, 0)
            else:
                logger.info("Mongo 总量: %d", cur_total)
            prev_total = cur_total
        except Exception:
            logger.exception("读取 Mongo 总量失败")

        # 保存进度（仅当成功时推进）
        if success:
            state[args.symbol] = page
            save_state(state_path, state)

    logger.info("抓取结束: pages %d..%d, inserted_estimate=%d, errors=%d",
                args.start, args.end, inserted_total, len(errors))
    if errors:
        logger.info("错误样本: %s", errors[:10])

if __name__ == "__main__":
    main()