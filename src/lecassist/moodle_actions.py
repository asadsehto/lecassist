"""Moodle actions behind the teacher forms.

Each function fills one Moodle form with Playwright. Every field on the teacher
forms maps to one argument here, so the forms (or any other UI) only have to
collect values and call these functions through the API in lecassist/server.
"""
import os
from contextlib import contextmanager
from datetime import datetime

from playwright.sync_api import sync_playwright

from lecassist.Moodle import call_moodle
from lecassist.browser import login, URL

username = os.environ["MOODLE_USER"]
password = os.environ["MOODLE_PASS"]


@contextmanager
def moodle_page(headless: bool = True):
    """Open a browser, log in as the teacher and give back the page."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        try:
            login(page, username, password)
            yield page
        finally:
            browser.close()


# ---------- small helpers for Moodle forms ----------

def open_section(page, fieldset_id: str):
    """Open a closed form section (like 'Grade') so its fields can be used."""
    section = page.locator(f"#{fieldset_id}")
    if "collapsed" in (section.get_attribute("class") or ""):
        section.locator(".fheader").first.click()


def set_datetime(page, field: str, when: datetime | None, has_toggle: bool = True):
    """Set a Moodle date field (5 dropdowns). None turns the date off."""
    toggle = page.locator(f"#id_{field}_enabled")
    if when is None:
        if has_toggle:
            toggle.uncheck()
        return
    if has_toggle:
        toggle.check()
    page.locator(f"#id_{field}_day").select_option(str(when.day))
    page.locator(f"#id_{field}_month").select_option(str(when.month))
    page.locator(f"#id_{field}_year").select_option(str(when.year))
    if page.locator(f"#id_{field}_hour").count():
        page.locator(f"#id_{field}_hour").select_option(str(when.hour))
        page.locator(f"#id_{field}_minute").select_option(str(when.minute))


def set_editor(page, field: str, text: str):
    """Type text into a Moodle rich text editor (TinyMCE)."""
    if not text:
        return
    body = page.frame_locator(f"#id_{field}_ifr").locator("body")
    body.click()
    body.fill(text)


def set_checkbox(page, field_id: str, on: bool):
    box = page.locator(f"#{field_id}")
    if on:
        box.check()
    else:
        box.uncheck()


def attach_files(page, paths: list[str]):
    """Upload files into the first file area of the form, one by one."""
    files = page.locator(".filemanager .fp-file")
    for path in paths:
        before = files.count()
        page.locator(".filemanager .fp-btn-add").first.click()
        page.get_by_text("Upload a file").click()
        page.wait_for_timeout(1000)  # the picker redraws its upload form; wait for it
        page.locator("input[name=repo_upload_file]").set_input_files(path)
        page.get_by_role("button", name="Upload this file").click()
        page.wait_for_function(
            "([sel, n]) => document.querySelectorAll(sel).length > n",
            arg=[".filemanager .fp-file", before],
        )


def save_form(page, button_id: str, form_url_part: str):
    """Click save and raise with Moodle's own messages if the form came back."""
    page.locator(f"#{button_id}").click()
    page.wait_for_load_state()
    if form_url_part in page.url:
        errors = page.locator(".invalid-feedback:visible, .error:visible").all_inner_texts()
        errors = [e.strip(" -\n") for e in errors if e.strip(" -\n")]
        raise RuntimeError("; ".join(errors) or "Moodle did not save the form")


def find_module(course_id: int, section: int, name: str) -> dict | None:
    """Find the newest activity with this name in a section (REST)."""
    for s in call_moodle("core_course_get_contents", courseid=course_id):
        if s["section"] == section:
            matches = [m for m in s["modules"] if m["name"] == name]
            if matches:
                m = max(matches, key=lambda m: m["id"])
                return {"cmid": m["id"], "url": m.get("url")}
    return None


# ---------- read lists for the forms ----------

def list_courses() -> list[dict]:
    me = call_moodle("core_webservice_get_site_info")
    courses = call_moodle("core_enrol_get_users_courses", userid=me["userid"])
    return [{"id": c["id"], "shortname": c["shortname"], "fullname": c["fullname"]}
            for c in sorted(courses, key=lambda c: c["fullname"].lower())]


def list_weeks(course_id: int) -> list[dict]:
    sections = call_moodle("core_course_get_contents", courseid=course_id)
    return [{"section": s["section"], "name": s["name"]} for s in sections]


def list_categories(page) -> list[dict]:
    """Categories this teacher may create courses in (read from Moodle's own form)."""
    page.goto(f"{URL}/course/edit.php")
    if page.locator("#id_category").count() == 0:
        raise RuntimeError("This account is not allowed to create courses")
    options = page.locator("#id_category option").evaluate_all(
        "o => o.map(x => [x.value, x.textContent.trim()])")
    return [{"id": int(v), "name": n} for v, n in options if v]


# ---------- the three actions ----------

def create_course(page, fullname: str, shortname: str, category_id: int,
                  start: datetime, end: datetime | None = None, weeks: int = 14,
                  summary: str = "", visible: bool = True) -> dict:
    page.goto(f"{URL}/course/edit.php?category={category_id}")
    page.locator("#id_fullname").fill(fullname)
    page.locator("#id_shortname").fill(shortname)
    page.locator("#id_visible").select_option("1" if visible else "0")
    set_datetime(page, "startdate", start, has_toggle=False)
    set_datetime(page, "enddate", end)
    set_editor(page, "summary_editor", summary)
    open_section(page, "id_courseformathdr")
    page.locator("#id_numsections").select_option(str(weeks))
    save_form(page, "id_saveanddisplay", "course/edit.php")
    course_id = int(page.url.split("id=")[1].split("&")[0].split("#")[0])
    return {"id": course_id, "url": f"{URL}/course/view.php?id={course_id}"}


def create_assignment(page, course_id: int, section: int, name: str, due: datetime,
                      description: str = "", show_description: bool = False,
                      allow_from: datetime | None = None, cutoff: datetime | None = None,
                      online_text: bool = False, file_submissions: bool = True,
                      max_files: int = 1, max_grade: int = 100,
                      attachments: list[str] | None = None,
                      visible: bool = True, notify_students: bool = False) -> dict:
    page.goto(f"{URL}/course/modedit.php?add=assign&course={course_id}&section={section}")
    page.locator("#id_name").fill(name)
    set_editor(page, "introeditor", description)
    set_checkbox(page, "id_showdescription", show_description)
    if attachments:
        attach_files(page, attachments)
    set_datetime(page, "allowsubmissionsfromdate", allow_from)
    set_datetime(page, "duedate", due)
    set_datetime(page, "cutoffdate", cutoff)
    set_datetime(page, "gradingduedate", None)  # avoids "remind me to grade" errors
    set_checkbox(page, "id_assignsubmission_onlinetext_enabled", online_text)
    set_checkbox(page, "id_assignsubmission_file_enabled", file_submissions)
    if file_submissions:
        page.locator("#id_assignsubmission_file_maxfiles").select_option(str(max_files))
    open_section(page, "id_modstandardgrade")
    page.locator("#id_grade_modgrade_point").fill(str(max_grade))
    open_section(page, "id_modstandardelshdr")
    page.locator("#id_visible").select_option("1" if visible else "0")
    set_checkbox(page, "id_coursecontentnotification", notify_students)
    save_form(page, "id_submitbutton2", "modedit.php")
    return find_module(course_id, section, name) or {}


def add_material(page, course_id: int, section: int, name: str, files: list[str],
                 description: str = "", show_description: bool = False,
                 visible: bool = True, notify_students: bool = False) -> dict:
    page.goto(f"{URL}/course/modedit.php?add=resource&course={course_id}&section={section}")
    page.locator("#id_name").fill(name)
    set_editor(page, "introeditor", description)
    set_checkbox(page, "id_showdescription", show_description)
    attach_files(page, files)
    open_section(page, "id_modstandardelshdr")
    page.locator("#id_visible").select_option("1" if visible else "0")
    set_checkbox(page, "id_coursecontentnotification", notify_students)
    save_form(page, "id_submitbutton2", "modedit.php")
    return find_module(course_id, section, name) or {}
