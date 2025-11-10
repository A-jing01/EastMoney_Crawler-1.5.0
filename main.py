import logging
import logging.config
try:
    logging.config.fileConfig('logging.conf', disable_existing_loggers=False)
except Exception:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(threadName)s - %(message)s",
        handlers=[
            logging.FileHandler("crawler.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
logger = logging.getLogger(__name__)
from crawler import PostCrawler
from crawler import CommentCrawler
import threading


def post_thread(stock_symbol, start_page, end_page):  # stock_symbol涓鸿偂绁ㄧ殑浠ｇ爜锛宲age涓烘兂瑕佺埇鍙栫殑椤甸潰鑼冨洿
    post_crawler = PostCrawler(stock_symbol)
    post_crawler.crawl_post_info(start_page, end_page)


def comment_thread_date(stock_symbol, start_date, end_date):  # stock_symbol涓鸿偂绁ㄧ殑浠ｇ爜锛宒ate涓烘兂瑕佺埇鍙栫殑鏃ユ湡鑼冨洿
    comment_crawler = CommentCrawler(stock_symbol)
    comment_crawler.find_by_date(start_date, end_date)
    comment_crawler.crawl_comment_info()


def comment_thread_id(stock_symbol, start_id, end_id):  # stock_symbol涓鸿偂绁ㄧ殑浠ｇ爜锛宨d鏄€氳繃post_id鏉ョ‘瀹氱埇鍙栵紝閫傚悎鏂仈缁埇
    comment_crawler = CommentCrawler(stock_symbol)
    comment_crawler.find_by_id(start_id, end_id)
    comment_crawler.crawl_comment_info()


if __name__ == "__main__":

    thread1 = threading.Thread(target=post_thread, args=('000333', 1, 10))
    thread2 = threading.Thread(target=post_thread, args=('000729', 1, 500))

    thread1.start()
    thread2.start()

    thread1.join()
    thread2.join()

    print(f"you have fetched data successfully, congratulations!")

