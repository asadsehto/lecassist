from playwright.sync_api import sync_playwright
import os
import time
username = os.environ["MOODLE_USER"]
password = os.environ["MOODLE_PASS"]
url = "http://localhost:8000"
login_url="http://localhost:8000/login/index.php"
    
with sync_playwright() as p:
    browser = p.chromium.launch(headless = False
                                , slow_mo = 500)
    page = browser.new_page()
    page.goto(url)
    print("title:", page.title())
    print("url:", page.url)
    page.screenshot(path="front.png")
    link = page.get_by_role("link" , name="log in")
    print("links found:", link.count())
    link.first.click()
    print("after click url:", page.url)
    print("title:", page.title())
    print("username boxes:", page.get_by_label("Username").count())
    page.screenshot(path="login.png")
    user_box = page.get_by_label("Username")
    user_box.fill(username)
    pass_box = page.get_by_label("Password")
    pass_box.fill(password)

    print("user_box now holds:", user_box.input_value())
    print("pass_box now holds:", pass_box.input_value())

    login = page.get_by_role("button", name="log in")
    login.first.click()
    time.sleep(3)
    browser.close()