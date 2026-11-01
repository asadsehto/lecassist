from playwright.sync_api import sync_playwright
import os
from datetime import datetime
from playwright.sync_api import sync_playwright
from lecassist.browser import login, create_assignment
from lecassist.Moodle import call_moodle
from lecassist.browser import login, create_assignment, upload_material
import os
import time
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
    upload_material(page, 2, 3, "Week 3 slides", pdf)
    browser.close()
    browser.close()

sections = call_moodle("core_course_get_contents", courseid=2)
print(sections[3]["name"], [(m["modname"], m["name"]) for m in sections[3]["modules"]])