import os
url      = os.environ["LOGIN_URL"]
def login(page, username: str, password: str):
        page.goto(url)
        page.get_by_label("username").fill(username)
        page.get_by_label("password").fill(password)
        page.get_by_role("button" , name = "log in").first.click()
        page.wait_for_load_state()
        if "/login/" in page.url:
            error = page.locator(".alert-danger").inner_text()
            raise RuntimeError("login failed: " + error)
        print("logged in, now at", page.url)
