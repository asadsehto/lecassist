from playwright.sync_api import sync_playwright
import os
from datetime import datetime
from lecassist.browser import login, create_assignment, upload_material, create_course, attach_file
from lecassist.Moodle import call_moodle, find_course , find_week
from lecassist.moodle_actions import set_enrolment_key
username = os.environ["MOODLE_USER"]
password = os.environ["MOODLE_PASS"]
URL      = os.environ["URL"]

def add_assignment(course: str, week: int, name: str, due: str, pdf_path: str = "") -> dict:
    """Create an assignment in a Moodle course under a given week.

    Args:
        course: course short name, for example AI101
        week: week number, for example 3
        name: assignment name
        due: due date and time as YYYY-MM-DD HH:MM, for example 2026-11-06 23:59
        pdf_path: full path of a PDF to attach, or empty for none
    """
    c = find_course(course)
    if c is None:
        return {"error": "no course with short name " + course}
    w = find_week(c["id"], week)
    if w is None:
        return {"error": "course " + course + " has no week " + str(week)}
    action = "create assignment '" + name + "' in " + c["shortname"] + " " + w["name"] + ", due " + due
    if pdf_path:
        action = action + ", attach " + pdf_path
    if not approve(action):
        return {"cancelled": "the teacher did not approve this"}
    try:
        due_date = datetime.strptime(due, "%Y-%m-%d %H:%M")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            login(page, username, password)
            create_assignment(page, c["id"], w["section"], name, due_date, pdf_path or None)
            browser.close()
    except Exception as e:
        return {"error": str(e)}
    return {"done": "assignment created", "course": c["shortname"], "week": week, "name": name, "due": due}

def add_course(fullname: str, shortname: str, weeks: int = 14, enrolment_key: str = "") -> dict:
    """Create a new Moodle course.

    Args:
        fullname: full course name, for example Machine Learning Lab
        shortname: unique short name, for example ML301
        weeks: number of weeks, 14 if not given
        enrolment_key: key students type to join the course, or empty for none
    """
    action = "create course '" + fullname + "' (" + shortname + ") with " + str(weeks) + " weeks"
    if enrolment_key:
        action = action + ", enrolment key " + enrolment_key
    if not approve(action):
        return {"cancelled": "the teacher did not approve this"}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            login(page, username, password)
            create_course(page, fullname, shortname, weeks)
            if enrolment_key:
                course_id = int(page.url.split("id=")[1].split("&")[0].split("#")[0])
                set_enrolment_key(page, course_id, enrolment_key)
            browser.close()
    except Exception as e:
        return {"error": str(e)}
    result = {"done": "course created", "fullname": fullname, "shortname": shortname}
    if enrolment_key:
        result["enrolment_key"] = enrolment_key
    return result

def add_material(course: str, week: int, name: str, file_path: str) -> dict:
    """Upload a file as course material under a given week of a Moodle course.

    Args:
        course: course short name, for example AI101
        week: week number, for example 3
        name: name students will see, for example Week 3 slides
        file_path: full path of the file to upload
    """
    c = find_course(course)
    if c is None:
        return {"error": "no course with short name " + course}
    w = find_week(c["id"], week)
    if w is None:
        return {"error": "course " + course + " has no week " + str(week)}
    if not approve("upload " + file_path + " as '" + name + "' to " + c["shortname"] + " " + w["name"]):
        return {"cancelled": "the teacher did not approve this"}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            login(page, username, password)
            upload_material(page, c["id"], w["section"], name, file_path)
            browser.close()
    except Exception as e:
        return {"error": str(e)}
    return {"done": "material uploaded", "course": c["shortname"], "week": week, "name": name}

def approve(action: str) -> bool:
    print("About to:", action)
    answer = input("Approve? (yes/no): ")
    return answer.strip().lower() == "yes"