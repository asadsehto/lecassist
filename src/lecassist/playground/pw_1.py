from playwright.sync_api import sync_playwright
import os
from datetime import datetime
from playwright.sync_api import sync_playwright
from lecassist.browser import login, create_assignment
from lecassist.Moodle import call_moodle
from lecassist.browser import login, create_assignment, upload_material
from lecassist.browser import login, create_assignment, upload_material, create_course
from lecassist.Moodle import call_moodle, find_course
username = os.environ["MOODLE_USER"]
password = os.environ["MOODLE_PASS"]
URL      = os.environ["URL"]

pdf = "/Users/asd/Downloads/IELTS_Graph_Vocabulary_Guide.pdf"
from lecassist.browser import login
with sync_playwright() as p:
    browser = p.chromium.launch(headless = False
                                , slow_mo = 1000)
    page = browser.new_page()
    login(page ,username , password)
    browser.close()

course = find_course("DL101")
print(course)
sections = call_moodle("core_course_get_contents", courseid=course["id"])
print(len(sections), sections[-1]["name"])