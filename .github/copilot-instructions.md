## 快速目标

帮助 AI 代码代理快速理解并在本仓库中高效工作：抓取东方财富（EastMoney）论坛帖子与评论，使用 Selenium 驱动浏览器并把解析结果写入 MongoDB。

## 关键概念（大局观）
- 主流程：PostCrawler/CommentCrawler（`crawler.py`）负责驱动浏览器获取页面元素 -> 交给 `parser.py` 的解析器生成字典 -> 用 `mongodb.py` 中的 `MongoAPI` 做幂等写入（`upsert_many` / `insert_many`）。
- WebDriver 管理：`WebDriverManager` 在每次启动时创建独立临时 profile（避免 profile 冲突），优先使用 `webdriver-manager`，回退到 `CHROME_DRIVER_PATH` 或 PATH 中的 `chromedriver`。
- 抗脆弱性：爬虫大量使用 `retry_on_driver_error` 装饰器和 `_restart_driver()` 方法来在可恢复错误时重试并重启 driver。

## 开发者工作流（常用命令/脚本）
- 快速自检：在项目根目录运行 `python .\quick_test.py`（会尝试启动 Chrome 与连接 MongoDB）。
- 运行主流程：编辑 `main.py` 中的参数，然后 `python .\main.py`（示例中以线程并发抓取多个股票代码）。
- 分页安全抓取：使用 `run_pages.py`，支持断点续抓（状态保存在 `run_pages_state.json`）：
  - 示例（PowerShell）: `python .\run_pages.py --symbol 000333 --start 1 --end 50 --headless`。

### 依赖与快速命令（PowerShell）
如果仓库中没有 `requirements.txt`，请先安装依赖：

```powershell
pip install selenium webdriver-manager pymongo pandas
# 运行快速自检（会尝试启动 Chrome 并连接 MongoDB）
python .\quick_test.py
# 在无 GUI 的环境测试 headless
$env:HEADLESS=1; python .\quick_test.py
```

## 项目约定与模式（必须遵守 / 常见陷阱）
- Parser 输出：`PostParser.parse_post_info` 与 `CommentParser.parse_comment_info` 返回简单的 dict（字段如 `post_url`, `post_title`, `post_date`, `post_time`, `post_author`, `comment_num` 等）。AI 修改解析器时请保持这些键名一致以兼容后续的 Mongo 写入逻辑。
- ID 与幂等：当 `post_url` 可用时，`PostCrawler` 将以 `md5(post_url)` 作为 `_id`。`MongoAPI.upsert_many` 以 `post_url` 为首选匹配键，回退到传入的 `id_field`（默认 `_id`）。修改去重/主键策略时需同时更新这两处逻辑。
- upsert_white-list：`MongoAPI.upsert_many` 使用白名单（`update_fields` / `insert_on_new`）做安全写入，避免把任意字段写入 `$set`。在改动字段写入行为时请修改 `mongodb.py` 中的默认白名单而不是在调用处散乱修改。
- 选择器与回退：`PostCrawler._fetch_list_page` 示范了「优先简洁 selector，未命中时回退更宽松选择器并过滤」的策略。添加新选择器时优先保持此模式以提高鲁棒性。

## 集成点与外部依赖
- Selenium + chromedriver（可用 `webdriver-manager` 自动下载）
- MongoDB（默认 localhost:27017，可通过 `MONGO_URI` 覆盖）
- 可选网络库：`requests` / `urllib3`（仅用于增强的网络判断/重试逻辑）

### 重要环境变量与优先级
- `MONGO_URI` — 若设置则优先使用（覆盖 host/port）。
- `CHROME_DRIVER_PATH` — 优先使用的 chromedriver 可执行路径（高于 PATH, 低于 webdriver-manager）。
- `CHROME_BINARY_PATH` — 指定 Chrome 可执行文件路径。
- `HEADLESS` — 若设为 `1` 则使用无头模式（也可通过构造参数 headless=True）。

优先级摘要（chromedriver）：webdriver-manager > CHROME_DRIVER_PATH > PATH
优先级摘要（Mongo）：MONGO_URI > explicit host/port

## 日志与调试
- 日志配置：项目提供 `logging.conf`，`main.py` 会尝试加载；默认会回退到写 `crawler.log`。遇到问题先查看 `crawler.log` 或控制台输出。
- 浏览器问题：若 Selenium 无法启动，检查 Chrome 与 chromedriver 的版本匹配，或设置环境变量 `CHROME_DRIVER_PATH` / `CHROME_BINARY_PATH`。
- Mongo 错误：`MongoAPI` 会在 BulkWriteError 时把详情写入 `bulk_write_error_details.json` 便于排查。

## 代码改动建议（AI 应遵守的实践）
- 修改解析（`parser.py`）时：保持返回字段名兼容；如果引入新字段，先在 `mongodb.py` 的白名单中声明如何写入（`update_fields` / `insert_on_new`）。
- 修改 driver 启动行为（`crawler.py` 中的 `WebDriverManager`）时：保证 temp profile 被清理（`quit_driver`），并保持 `create_driver` 中对 `CHROME_DRIVER_PATH` 与 `webdriver-manager` 的回退逻辑。
- 异常处理：仓库倾向于记录异常并继续（保证长期运行）。AI 对长任务的改动不要轻易把可恢复异常改为终止流程。

### 新字段/结构变更检查清单（必须遵守）
当需要新增或修改 parser 输出字段（例如新增 `post_category`）时，请按此顺序执行并在 PR 中说明：
1. 在 `parser.py` 的 `PostParser.parse_post_info` 中新增字段并保证 key 名称稳定；确保字段类型在所有分支中一致。
2. 在 `mongodb.py::MongoAPI.upsert_many` 中判断该字段应为静态还是可更新，并把它加入对应白名单：`insert_on_new`（首次插入）或 `update_fields`（后续更新）。
3. 若变更影响去重或主键策略（例如不再使用 `md5(post_url)`），同时修改 `PostCrawler._parse_and_store` 中的 `_id` 生成与去重逻辑。
4. 运行 `python .\quick_test.py`（或相应测试），监控 `crawler.log` 和仓库根目录的 `bulk_write_error_details.json`。
5. 在 PR 描述中列出受影响 collection（例如 `post_000333`）和预期写入行为。

## 快速示例片段（参考）
- 幂等写入（简化说明）: PostCrawler 在写入前将有 URL 的文档设置 `_id = md5(post_url)` -> 调用 `MongoAPI.upsert_many(unique_docs, id_field='_id')`。
- 重试装饰器：在可能抛出 `WebDriverException` 的方法上使用 `@retry_on_driver_error(max_attempts=4)`，该装饰器会尝试调用实例的 `_restart_driver()`。

### 常用文档样例（生成 parser 时请对齐）
- Post doc keys: `_id`（若有 `post_url` 则为 md5(post_url)）、`post_url`, `post_title`, `post_date`, `post_time`, `post_author`, `post_view`, `comment_num`, `last_crawled`
- Comment doc keys: `post_id`, `comment_content`, `comment_like`, `comment_date`, `comment_time`, `sub_comment`

## 参考文件
- `crawler.py`（WebDriver 管理、PostCrawler、CommentCrawler、retry 逻辑）
- `parser.py`（PostParser / CommentParser，字段与解析细节）
- `mongodb.py`（MongoAPI，upsert/insert 的实现与错误处理）
- `run_pages.py`（断点续抓、速率控制与安全退出逻辑）
- `quick_test.py`（快速环境自检脚本）
- `README.md`（环境依赖与快速上手）

## 调试 BulkWriteError（快速操作步骤）
1. 检查仓库根目录下 `bulk_write_error_details.json`（包含 Mongo 返回的详细信息）。
2. 在 `crawler.log` 中搜索相关异常栈与被跳过的文档信息。
3. 常见原因：字段类型冲突（字符串 vs 数值）、字段过长或索引唯一约束冲突。修复方法：在 parser 中标准化类型或调整 `upsert_many` 白名单以避免把该字段放入 `$set`。

## 小结 / 我可以帮你的事
- 我可以生成 `requirements.txt`（包含 selenium, webdriver-manager, pymongo, pandas），并提交为 PR。
- 我可以把“新增字段变更流程”做成 CI 检查步骤或 PR 模板。
- 如果你希望，我会把本文件再收紧为 20-30 行的超精简版本。

---
如果需要我可以将其中某些段落扩展为更详细的编码规则（例如如何为新字段添加测试、如何在 CI 中运行 quick_test.py、或将 `upsert_many` 的返回格式标准化）。请告诉我你想优先补充的部分。 
