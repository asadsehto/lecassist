"""Checks whether LecAssist can work on a Moodle site with this teacher's account.

    uv run python -m lecassist.check_moodle

Asks for the site, username and password (the password is not shown or saved).
Only reads: nothing is created or changed on the site.
"""
import getpass
import json
import os
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

# Every Moodle function LecAssist calls, and what it is used for.
NEEDED = {
    "core_webservice_get_site_info": "read who is signed in",
    "core_enrol_get_users_courses": "list the teacher's courses",
    "core_course_get_contents": "list the weeks of a course",
    "mod_assign_get_assignments": "list assignments",
    "core_enrol_get_enrolled_users": "list the students in a course (marks)",
    "mod_assign_get_grades": "read marks",
    "mod_assign_save_grade": "save marks",
}

results = []


def report(ok: bool, what: str, why: str = ""):
    results.append(ok)
    print(("  OK    " if ok else "  NO    ") + what + ("" if ok else "  ->  " + why))


def get_json(url: str, data: dict | None = None):
    body = urllib.parse.urlencode(data).encode() if data else None
    with urllib.request.urlopen(url, data=body, timeout=30) as r:
        return json.loads(r.read().decode())


def check_api(site: str, username: str, password: str):
    print("\nThe eLearning connection (API)")
    try:
        answer = get_json(site + "/login/token.php",
                          {"service": "moodle_mobile_app", "username": username, "password": password})
    except Exception as e:
        report(False, "Reach the site", str(e))
        return None
    if "token" not in answer:
        if answer.get("errorcode") == "enablewsdescription":
            report(False, "Connection switched on", "IBA has to switch on web services and the mobile app service")
        elif answer.get("errorcode") == "invalidlogin":
            report(False, "Sign in", "wrong username or password")
        else:
            report(False, "Connection switched on", answer.get("error", str(answer)))
        return None
    report(True, "Connection switched on and sign-in works")
    token = answer["token"]
    info = get_json(site + "/webservice/rest/server.php?" + urllib.parse.urlencode(
        {"wstoken": token, "wsfunction": "core_webservice_get_site_info", "moodlewsrestformat": "json"}))
    allowed = {f["name"] for f in info.get("functions", [])}
    print("  Moodle " + str(info.get("release", "?")) + ", signed in as " + str(info.get("fullname", "?")))
    for name, use in NEEDED.items():
        report(name in allowed, "Can " + use, "IBA has to add " + name + " to the mobile app service")
    courses = get_json(site + "/webservice/rest/server.php?" + urllib.parse.urlencode(
        {"wstoken": token, "wsfunction": "core_enrol_get_users_courses", "moodlewsrestformat": "json",
         "userid": info.get("userid")}))
    if isinstance(courses, list) and courses:
        report(True, "Sees " + str(len(courses)) + " course(s)")
        return courses[0]["id"]
    report(False, "Sees the teacher's courses", "this account is not a teacher in any course")
    return None


def check_browser(site: str, username: str, password: str, course_id):
    print("\nThe eLearning pages (browser)")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(site + "/login/index.php")
        page.locator("#username").fill(username)
        page.locator("#password").fill(password)
        page.locator("#loginbtn").click()
        page.wait_for_load_state()
        if "/login/" in page.url:
            report(False, "Sign in on the website", "wrong username or password")
            browser.close()
            return
        report(True, "Sign in on the website")
        if course_id is None:
            link = page.locator("a[href*='/course/view.php?id=']").first
            if link.count():
                course_id = int(link.get_attribute("href").split("id=")[1].split("&")[0])
        if course_id is None:
            report(False, "Open a course", "no course found for this account")
        else:
            for kind, label, fields in [("assign", "Create assignments (with due date and files)",
                                         ["#id_name", "#id_duedate_day", ".filemanager"]),
                                        ("resource", "Upload material to a week", ["#id_name", ".filemanager"])]:
                page.goto(f"{site}/course/modedit.php?add={kind}&course={course_id}&section=1")
                missing = [f for f in fields if page.locator(f).count() == 0]
                report(not missing, label, "the form is different here: " + ", ".join(missing))
        page.goto(site + "/course/edit.php")
        report(page.locator("#id_fullname").count() > 0, "Create courses",
               "this account is not allowed to create courses")
        browser.close()


def main():
    print("LecAssist check. Nothing is changed on eLearning.\n")
    site = (os.environ.get("CHECK_SITE") or input("eLearning address (e.g. http://lmst.iba-suk.edu.pk): ")).strip().rstrip("/")
    username = os.environ.get("CHECK_USER") or input("Username: ").strip()
    password = os.environ.get("CHECK_PASS") or getpass.getpass("Password (not shown): ")
    course_id = check_api(site, username, password)
    check_browser(site, username, password, course_id)
    print("\n" + ("Everything LecAssist needs works on this site."
                  if all(results) else "LecAssist will not fully work yet. Send the NO lines to IBA's eLearning admin."))


if __name__ == "__main__":
    main()
