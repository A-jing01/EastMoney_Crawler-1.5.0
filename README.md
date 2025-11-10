# EastMoney_Crawler

简要说明与快速上手指南。

## 功能
这是一个爬取东方财富帖子与评论的爬虫项目，使用 Selenium 驱动浏览器抓取帖子、评论并写入 MongoDB。

## 先决条件
- Python 3.8+（你当前环境是 Python 3.12）
- Chrome 浏览器
- chromedriver（或使用 webdriver-manager 自动下载）
- MongoDB（本地或远程，默认 localhost:27017）
- 推荐安装依赖：
  pip install selenium webdriver-manager pymongo pandas

## 环境变量（可选）
- CHROME_DRIVER_PATH: 指定 chromedriver 可执行文件路径（优先）
- CHROME_BINARY_PATH: 指定 Chrome 浏览器可执行文件路径（可选）
- HEADLESS: 若为 `1` 则以无头模式运行（可选）
- MONGO_URI: 指定 MongoDB 连接 URI（如 mongodb://user:pass@host:27017/），若不设置则默认连接 `mongodb://localhost:27017`

## 快速自检
在项目根目录运行：
python .\quick_test.py

该脚本会尝试启动 Chrome（会优先使用 webdriver-manager，如失败则使用 `CHROME_DRIVER_PATH` 或 PATH 中的 chromedriver），并连接 MongoDB，打印结果。

## 运行爬虫
编辑 `main.py` 中你要抓取的股票代码/页码，确保 MongoDB 在运行，然后：
python .\main.py

## 日志
- 默认日志文件：`crawler.log`
- 如果想使用配置文件 `logging.conf`，可以在 `main.py` 中通过 `logging.config.fileConfig('logging.conf')` 加载（示例见下方）。

## 故障排查
- 如果 Selenium 无法启动，先确认 Chrome 与 chromedriver 匹配，并设置 `CHROME_DRIVER_PATH` 与/或 `CHROME_BINARY_PATH`。
- 若 Mongo 连接被拒绝，确认 MongoDB 服务已启动，或使用 `MONGO_URI` 指向正确地址。
