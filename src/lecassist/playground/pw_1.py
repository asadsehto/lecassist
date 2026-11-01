from playwright.sync_api import sync_playwright
import os
import time
username = os.environ["MOODLE_USER"]
password = os.environ["MOODLE_PASS"]
URL      = os.environ["URL"]
from lecassist.browser import login
with sync_playwright() as p:
    browser = p.chromium.launch(headless = False
                                , slow_mo = 500)
    page = browser.new_page()
    login(page ,username , password)
    print("title:", page.title())
    print("url:", page.url)
    page.screenshot(path="front.png")
    page.goto(URL + "/course/view.php?id=2")
    print("course page title:", page.title())

    time.sleep(3)
    browser.close()