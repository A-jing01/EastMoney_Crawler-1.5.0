from selenium.webdriver.common.by import By
from selenium import webdriver
from datetime import datetime
import re


class PostParser(object):

    def __init__(self):
        self.year = None
        self.month = 13
        self.id = 0

    @staticmethod
    def parse_post_title(html):
        # 尝试多种选择器以兼容不同 DOM
        try:
            a = html.find_element(By.CSS_SELECTOR, 'td:nth-child(3) a')
            txt = a.text.strip()
            if txt:
                return txt
        except Exception:
            pass
        try:
            title_element = html.find_element(By.CSS_SELECTOR, 'td:nth-child(3) > div')
            return title_element.text.strip()
        except Exception:
            return ""

    @staticmethod
    def parse_post_view(html):
        # 阅读数通常在第一列的 div.read
        try:
            view_element = html.find_element(By.CSS_SELECTOR, 'td:nth-child(1) div.read')
            return view_element.text.strip()
        except Exception:
            try:
                view_element = html.find_element(By.CSS_SELECTOR, 'td:nth-child(1) > div')
                return view_element.text.strip()
            except Exception:
                return ""

    @staticmethod
    def parse_comment_num(html):
        """
        更稳健的评论数解析：支持纯数字、带 '万' 的数、并在异常情况下返回 0。
        """
        try:
            num_element = html.find_element(By.CSS_SELECTOR, "td:nth-child(2) > div")
            text = (num_element.text or "").strip()
        except Exception:
            return 0

        if not text:
            return 0

        # 移除千位分隔符
        cleaned = text.replace(",", "")

        # 纯数字
        if cleaned.isdigit():
            try:
                return int(cleaned)
            except Exception:
                return 0

        # 以 '万' 结尾的情况（如 1.2万）
        try:
            if cleaned.endswith("万"):
                num_part = cleaned[:-1].strip()
                return int(float(num_part.replace(",", "")) * 10000)
        except Exception:
            pass

        # 退路：从字符串中提取第一个数字（支持小数）
        m = re.search(r'(\d[\d,\.]*)', cleaned)
        if m:
            s = m.group(1).replace(",", "")
            try:
                if "." in s:
                    return int(float(s))
                return int(s)
            except Exception:
                return 0

        return 0

    @staticmethod
    def parse_post_url(html):
        try:
            url_element = html.find_element(By.CSS_SELECTOR, 'td:nth-child(3) > div > a')
            href = url_element.get_attribute('href') or ""
        except Exception:
            try:
                a = html.find_element(By.CSS_SELECTOR, 'td:nth-child(3) a')
                href = a.get_attribute('href') or ""
            except Exception:
                href = ""

        href = href.strip()
        # 有些 href 是相对路径 "/news,000333,xxxx.html"
        if href.startswith("/"):
            return "https://guba.eastmoney.com" + href
        return href

    @staticmethod
    def remove_char(date_str):
        # 使用正则去掉所有非数字/空格/冒号/连字符字符（处理包含汉字的情况）
        cleaned_str = re.sub(r'[^\d\s:-]', '', date_str)
        return cleaned_str.strip()

    def get_post_year(self, html):
        # 不再自动打开新的 webdriver，改为使用当前年份作为默认
        from datetime import datetime
        self.year = datetime.now().year
        # 如果有其它更可靠的年信息在页面上，可在此解析

    @staticmethod
    def judge_post_date(html):
        try:
            judge_element = html.find_element(By.CSS_SELECTOR, 'td:nth-child(3) > div > span')
            if judge_element.text == '问董秘':
                return False
        except Exception:
            return True
        return True

    def parse_post_date(self, html):
        # 尝试多个可能的选择器获取日期时间（页面上通常显示 MM-DD HH:MM）
        time_str = None
        selectors = [
            'td:nth-child(5) > div',
            'td:nth-child(5) > div.update',
            'td:nth-child(5) > div.update.mod_time',
            'div.update.pub_time',
            'div.update.mod_time'
        ]
        for sel in selectors:
            try:
                el = html.find_element(By.CSS_SELECTOR, sel)
                time_str = el.text.strip()
                if time_str:
                    break
            except Exception:
                continue

        if not time_str:
            return None, None

        # 常见格式: "11-05 16:31"
        try:
            date_part, time_part = time_str.split(' ')
            month, day = map(int, date_part.split('-'))
        except Exception:
            return None, None

        if self.judge_post_date(html):
            if self.month < month == 12:
                if self.year is not None:
                    self.year -= 1
            self.month = month

        if self.year is None:
            self.get_post_year(html)

        date = f'{self.year}-{month:02d}-{day:02d}'
        time_val = time_part[:5]
        return date, time_val

    @staticmethod
    def parse_post_author(html):
        try:
            author_element = html.find_element(By.CSS_SELECTOR, 'td:nth-child(4) > div')
            # 尝试找到 a.nametext
            try:
                a = author_element.find_element(By.CSS_SELECTOR, 'a.nametext')
                return a.text.strip()
            except Exception:
                return author_element.text.strip()
        except Exception:
            return ""

    def parse_post_info(self, html):
        self.id += 1
        title = self.parse_post_title(html)
        view = self.parse_post_view(html)
        num = self.parse_comment_num(html)
        url = self.parse_post_url(html)
        date, time = self.parse_post_date(html)
        author = self.parse_post_author(html)
        post_info = {
            '_id': self.id,
            'post_title': title,
            'post_view': view,
            'comment_num': num,
            'post_url': url,
            'post_date': date,
            'post_time': time,
            'post_author': author
        }
        return post_info


class CommentParser(object):

    @staticmethod
    def judge_sub_comment(html):  # identify whether it has sub-comments
        sub = html.find_elements(By.CSS_SELECTOR, 'ul.replyListL2')  # must use '_elements' instead of '_element'
        return bool(sub)  # if not null return True, vice versa, return False

    @staticmethod
    def parse_comment_content(html, sub_bool):
        if sub_bool:  # situation to deal with sub-comments
            content_element = html.find_element(By.CSS_SELECTOR, 'div.reply_title > span')
        else:
            content_element = html.find_element(By.CSS_SELECTOR, 'div.recont_right.fl > div.reply_title > span')
        return content_element.text

    @staticmethod
    def parse_comment_like(html, sub_bool):
        if sub_bool:  # situation to deal with sub-comments
            like_element = html.find_element(By.CSS_SELECTOR, 'span.likemodule')
        else:
            like_element = html.find_element(By.CSS_SELECTOR, 'ul.bottomright > li:nth-child(4) > span')

        if like_element.text == '点赞':  # website display text instead of '0'
            return 0
        else:
            try:
                return int(like_element.text)
            except Exception:
                return 0

    @staticmethod
    def parse_comment_date(html, sub_bool):
        if sub_bool:  # situation to deal with sub-comments
            date_element = html.find_element(By.CSS_SELECTOR, 'span.pubtime')
        else:
            date_element = html.find_element(By.CSS_SELECTOR, 'div.publishtime > span.pubtime')
        date_str = date_element.text
        date = date_str.split(' ')[0]
        time = date_str.split(' ')[1][:5]
        return date, time

    def parse_comment_info(self, html, post_id, sub_bool: bool = False):  # sub_pool is used to distinguish sub-comments
        content = self.parse_comment_content(html, sub_bool)
        like = self.parse_comment_like(html, sub_bool)
        date, time = self.parse_comment_date(html, sub_bool)
        whether_subcomment = int(sub_bool)  # '1' means it is sub-comment, '0' means it is not
        comment_info = {
            'post_id': post_id,
            'comment_content': content,
            'comment_like': like,
            'comment_date': date,
            'comment_time': time,
            'sub_comment': whether_subcomment,
        }
        return comment_info
