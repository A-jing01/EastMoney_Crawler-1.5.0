from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

chromedriver = r"C:\Users\啊景\AppData\Local\Google\Chrome\Application\chromedriver.exe"
chrome_bin = r"C:\Users\啊景\AppData\Local\Google\Chrome\Application\chrome.exe"  # 或 D:\软件\生产力\chrome.exe

service = Service(chromedriver)
opts = Options()
opts.binary_location = chrome_bin
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--disable-gpu")
opts.add_argument("--remote-debugging-port=9222")
# opts.add_argument("--headless=new")  # 可尝试无头模式

driver = webdriver.Chrome(service=service, options=opts)
driver.get("https://www.baidu.com")
print(driver.title)
driver.quit()