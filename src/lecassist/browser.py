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

URL = os.environ["URL"]


def set_date(page, field: str, when):
    page.locator(f"#id_{field}_enabled").check()
    page.locator(f"#id_{field}_day").select_option(str(when.day))
    page.locator(f"#id_{field}_month").select_option(str(when.month))
    page.locator(f"#id_{field}_year").select_option(str(when.year))
    page.locator(f"#id_{field}_hour").select_option(str(when.hour))
    page.locator(f"#id_{field}_minute").select_option(str(when.minute))


def attach_file(page, path: str):
    page.locator(".filemanager .fp-btn-add").first.click()
    page.get_by_text("Upload a file").click()
    page.wait_for_timeout(1000)
    page.locator("input[name=repo_upload_file]").set_input_files(path)
    page.get_by_role("button", name="Upload this file").click()
    page.locator(".filemanager .fp-file").first.wait_for()


def create_assignment(page, course_id: int, section: int, name: str, due, pdf_path=None):
    page.goto(f"{URL}/course/modedit.php?add=assign&course={course_id}&section={section}")
    page.locator("#id_name").fill(name)
    set_date(page, "duedate", due)
    page.locator("#id_gradingduedate_enabled").uncheck()
    if pdf_path:
        attach_file(page, pdf_path)
    page.locator("#id_submitbutton2").click()
    page.wait_for_load_state()
    if "modedit.php" in page.url:
        errors = page.locator(".invalid-feedback:visible").all_inner_texts()
        raise RuntimeError("not saved: " + " | ".join(errors))
    print("saved, now at", page.url)

def upload_material(page, course_id: int, section: int, name: str, file_path: str):
    page.goto(f"{URL}/course/modedit.php?add=resource&course={course_id}&section={section}")
    page.locator("#id_name").fill(name)
    if file_path:
         attach_file(page, file_path)
    page.locator("#id_submitbutton2").click()
    page.wait_for_load_state()
    if "modedit.php" in page.url:
            errors = page.locator(".invalid-feedback:visible").all_inner_texts()
            raise RuntimeError("not saved: " + " | ".join(errors))
    print("saved, now at", page.url)

def create_course(page, fullname: str, shortname: str , weeks:int=14):
     page.goto(f"http://localhost:8000/course/edit.php?category=1")
     page.locator("#id_fullname").fill(fullname)
     page.locator("#id_shortname").fill(shortname)
     page.locator("#id_courseformathdr .fheader").click()
     page.locator("#id_numsections").select_option(str(weeks))
     page.locator("#id_saveanddisplay").click()
     if "course/edit.php" in page.url:
        errors = page.locator(".invalid-feedback:visible").all_inner_texts()
        raise RuntimeError("not saved: " + " | ".join(errors))
     print("saved, now at", page.url)


    