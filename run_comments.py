import argparse
import time
import random
import json
import logging
from pathlib import Path

logger = logging.getLogger("run_comments")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(ch)

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
    if crawler is None:
        return
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

def try_call_comment_method(crawler, post):
    url = post.get('post_url')
    pid = post.get('_id')

    candidates = ['crawl_comment_info', 'crawl_post_comments', 'crawl_comments', 'fetch_comments', 'fetch_comment_info']

    for name in candidates:
        if not hasattr(crawler, name):
            continue
        meth = getattr(crawler, name)
        try:
            # 优先用 list 形式传入单个 URL 或 id（方法通常期望 iterable/list）
            if url:
                try:
                    meth([url])
                except TypeError:
                    # 如果方法接受单个字符串作为参数，也尝试传入字符串
                    meth(url)
            elif pid is not None:
                try:
                    meth([pid])
                except TypeError:
                    meth(pid)
            else:
                # 无参数调用
                meth()
            return True
        except Exception as e:
            logger.exception("调用 %s 失败: %s", name, e)
            # 继续尝试下一个候选
    logger.warning("没有找到或成功调用兼容的评论抓取方法")
    return False

def main():
    parser = argparse.ArgumentParser(description="Run comment crawler on posts from Mongo")
    parser.add_argument("--symbol", default="000333")
    parser.add_argument("--start", type=int, default=0, help="从第 n 条(post 排序) 开始，0 表示第 1 条")
    parser.add_argument("--limit", type=int, default=5, help="抓取多少条帖子用于测试")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--state-file", default="run_comments_state.json")
    parser.add_argument("--max-retries", type=int, default=2)
    args = parser.parse_args()

    state_path = Path(args.state_file)
    state = load_state(state_path)
    last_done = state.get(args.symbol, -1)
    start_index = max(args.start, last_done + 1)

    logger.info("开始抓取评论 symbol=%s start_index=%d limit=%d headless=%s (resume from %d)",
                args.symbol, start_index, args.limit, args.headless, last_done)

    # connect to Mongo posts
    try:
        from mongodb import MongoAPI
        m_posts = MongoAPI("post_info", f"post_{args.symbol}")
    except Exception as e:
        logger.exception("无法连接到 posts 集合: %s", e)
        return

    # fetch target posts
    posts = m_posts.find({}, projection=None)
    if not posts:
        logger.info("没有找到任何帖子，退出")
        return

    # slice to work set
    work_posts = posts[start_index:start_index + args.limit]
    logger.info("将处理 %d 条帖子 (index %d..%d)", len(work_posts), start_index, start_index + len(work_posts) - 1)

    for idx, post in enumerate(work_posts, start=start_index):
        page_index = idx
        logger.info("处理帖子 index=%d, _id=%s, url=%s", page_index, post.get("_id"), post.get("post_url"))
        attempt = 0
        success = False
        while attempt <= args.max_retries and not success:
            attempt += 1
            crawler = None
            try:
                # 动态导入 CommentCrawler
                from crawler import CommentCrawler
                crawler = CommentCrawler(args.symbol, headless=args.headless)
                ok = try_call_comment_method(crawler, post)
                if not ok:
                    logger.error("无法调用 CommentCrawler 的兼容方法，跳过此帖子")
                    success = False
                    break
                success = True
            except Exception as e:
                logger.exception("page index %d 抓取评论出错 attempt %d: %s", page_index, attempt, e)
                if attempt <= args.max_retries:
                    backoff = 1.0 * (2 ** (attempt - 1))
                    logger.info("将在 %.1fs 后重试", backoff)
                    time.sleep(backoff)
                else:
                    logger.error("page index %d 最终失败: %s", page_index, e)
            finally:
                try:
                    safe_quit_crawler(crawler)
                except Exception:
                    pass

        # 保存进度（若成功）
        if success:
            state[args.symbol] = page_index
            save_state(state_path, state)

        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        logger.info("帖子 index=%d 处理完 success=%s, 睡眠 %.1fs", page_index, success, delay)
        time.sleep(delay)

    logger.info("评论抓取任务完成")

if __name__ == "__main__":
    main()