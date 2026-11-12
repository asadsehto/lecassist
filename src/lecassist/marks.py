"""Marks from an Excel sheet to an eLearning assignment.

0. course_items() lists the assignments and quizzes that take marks
1. read_sheet()  reads Name / CMS / Marks (and Email, if the sheet has it)
2. match_rows()  finds each row's student on eLearning: by email, then by the
                 CMS -> email pairs remembered from earlier uploads, then by name.
                 Two students with the same name are never guessed; the teacher picks.
3. save_marks()  saves each mark (assignments through the API, quizzes through
                 the gradebook page), then reads the marks back to confirm.
"""
import csv
import io
import json
import re
from pathlib import Path

from openpyxl import load_workbook

from lecassist.Moodle import call_moodle

# CMS -> email pairs the teacher confirmed, so the next sheet matches by CMS.
MEMORY = Path.home() / ".lecassist" / "cms_emails.json"

HEADERS = {
    "name": ("name", "student name", "full name", "student"),
    "cms": ("cms", "cms id", "cmsid", "cms no", "id", "reg no", "registration", "registration no", "roll no"),
    "marks": ("marks", "mark", "score", "grade", "total", "obtained"),
    "email": ("email", "e-mail", "email address"),
}


def clean(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def key(text) -> str:
    return clean(text).lower()


def read_sheet(filename: str, data: bytes) -> list[dict]:
    """Rows of {"row", "name", "cms", "email", "marks"} from .xlsx or .csv."""
    if filename.lower().endswith(".csv"):
        table = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
    else:
        sheet = load_workbook(io.BytesIO(data), read_only=True, data_only=True).active
        table = [list(r) for r in sheet.iter_rows(values_only=True)]
    # the header is the first row that has a name or CMS column and a marks column
    for h, header in enumerate(table[:15]):
        cols = {}
        for i, cell in enumerate(header):
            for field, names in HEADERS.items():
                if key(cell) in names and field not in cols:
                    cols[field] = i
        if "marks" in cols and ("name" in cols or "cms" in cols or "email" in cols):
            break
    else:
        raise ValueError("Could not find the columns. The sheet needs a Marks column and a Name, CMS or Email column.")
    rows = []
    for n, r in enumerate(table[h + 1:], start=h + 2):
        get = lambda f: clean(r[cols[f]]) if f in cols and cols[f] < len(r) and r[cols[f]] is not None else ""
        if not any(get(f) for f in cols):
            continue
        rows.append({"row": n, "name": get("name"), "cms": get("cms"), "email": get("email"), "marks": get("marks")})
    return rows


def course_students(course_id: int) -> list[dict]:
    users = call_moodle("core_enrol_get_enrolled_users", courseid=course_id)
    return [{"id": u["id"], "name": u["fullname"], "email": u.get("email", "")}
            for u in users if any(r["shortname"] == "student" for r in u.get("roles", []))]


def gradebook_items(course_id: int) -> dict:
    """{(module, instance): gradebook item}. Empty while the course has no students."""
    report = call_moodle("gradereport_user_get_grade_items", courseid=course_id)["usergrades"]
    if not report:
        return {}
    return {(g["itemmodule"], g["iteminstance"]): g for g in report[0]["gradeitems"] if g.get("itemtype") == "mod"}


def course_items(course_id: int) -> list[dict]:
    """Every assignment and quiz on the course page, in page order."""
    assignments = {a["id"]: a for c in call_moodle("mod_assign_get_assignments", **{"courseids[0]": course_id})["courses"]
                   for a in c["assignments"]}
    gradebook = gradebook_items(course_id)
    items = []
    for section in call_moodle("core_course_get_contents", courseid=course_id):
        for m in section["modules"]:
            if m["modname"] == "assign":
                top = float(assignments.get(m["instance"], {}).get("grade", 0))
            elif m["modname"] == "quiz":
                top = float(gradebook.get(("quiz", m["instance"]), {}).get("grademax") or 0)
            else:
                continue
            items.append({"key": m["modname"] + ":" + str(m["instance"]),
                          "kind": "quiz" if m["modname"] == "quiz" else "assignment",
                          "instance": m["instance"], "name": m["name"], "max": top, "week": section["name"]})
    return items


def stored_marks(course_id: int, item: dict) -> dict:
    """{student id: mark} as eLearning has it now."""
    module = "quiz" if item["kind"] == "quiz" else "assign"
    report = call_moodle("gradereport_user_get_grade_items", courseid=course_id)["usergrades"]
    out = {}
    for u in report:
        for g in u["gradeitems"]:
            if g.get("itemmodule") == module and g.get("iteminstance") == item["instance"] and g.get("graderaw") is not None:
                out[u["userid"]] = float(g["graderaw"])
    return out


def norm(text) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def find_course_and_item(text: str, courses: list[dict], course_id: int | None) -> tuple[int | None, dict | None, str]:
    """Find the course and the assignment/quiz a sentence like "Quiz 1 of AI101" means.
    Returns (course id, item, problem)."""
    said = norm(text)
    if course_id is None:
        hits = [c for c in courses if norm(c["shortname"]) and norm(c["shortname"]) in said]
        if len(hits) != 1:
            return None, None, "Say which course, e.g. " + (courses[0]["shortname"] if courses else "AI101") + ", or choose it."
        course_id = hits[0]["id"]
    items = course_items(course_id)
    hits = [i for i in items if norm(i["name"]) and norm(i["name"]) in said]
    if len(hits) > 1:  # "Lab 3" inside "Lab 3 with PDF": keep the longest name
        longest = max(len(norm(i["name"])) for i in hits)
        hits = [i for i in hits if len(norm(i["name"])) == longest]
    if len(hits) == 1:
        return course_id, hits[0], ""
    names = ", ".join(i["name"] for i in items)
    if len(hits) > 1:
        return course_id, None, "More than one item is called " + hits[0]["name"] + ". Choose it from the list."
    return course_id, None, "Say which assignment or quiz. This course has: " + names + "."


def remembered() -> dict:
    try:
        return json.loads(MEMORY.read_text())
    except (OSError, ValueError):
        return {}


def remember(pairs: dict):
    if not pairs:
        return
    MEMORY.parent.mkdir(parents=True, exist_ok=True)
    MEMORY.write_text(json.dumps(remembered() | pairs, indent=1))


def match_rows(rows: list[dict], students: list[dict], max_mark: float) -> list[dict]:
    """Adds "student" (id or None), "choices", "mark" and "problem" to each row."""
    by_email = {key(s["email"]): s for s in students if s["email"]}
    by_name = {}
    for s in students:
        by_name.setdefault(key(s["name"]), []).append(s)
    memory = remembered()
    used = {}
    for r in rows:
        r["student"], r["choices"], r["problem"], r["how"] = None, [], "", ""
        email = key(r["email"]) or key(memory.get(key(r["cms"]), ""))
        if email and email in by_email:
            r["student"], r["how"] = by_email[email]["id"], "email" if r["email"] else "remembered CMS"
        elif key(r["name"]) in by_name and len(by_name[key(r["name"])]) == 1:
            r["student"], r["how"] = by_name[key(r["name"])][0]["id"], "name"
        elif key(r["name"]) in by_name:
            r["choices"] = [s["id"] for s in by_name[key(r["name"])]]
            r["problem"] = "Two or more students have this name. Choose the right one."
        else:
            r["problem"] = "No student in this course with this name or email. Choose one or skip."
        # the mark
        try:
            r["mark"] = float(r["marks"])
            if not 0 <= r["mark"] <= max_mark:
                r["problem"] = r["problem"] or f"Mark must be between 0 and {max_mark:g}."
        except ValueError:
            r["mark"] = None
            r["problem"] = r["problem"] or "Mark is not a number."
        if r["student"] is not None:
            used.setdefault(r["student"], []).append(r["row"])
    for student, sheet_rows in used.items():
        if len(sheet_rows) > 1:
            for r in rows:
                if r["student"] == student:
                    r["problem"] = r["problem"] or "Same student on rows " + ", ".join(map(str, sheet_rows)) + "."
    return rows


def save_marks(course_id: int, item: dict, marks: list[dict], students: list[dict], page=None) -> list[dict]:
    """marks: [{"student", "mark", "cms"}]. Assignments through the API, quizzes through
    the gradebook page (needs a logged-in `page`). Reads back, remembers CMS -> email."""
    results = []
    if item["kind"] == "assignment":
        feedback = {"plugindata[assignfeedbackcomments_editor][text]": "",
                    "plugindata[assignfeedbackcomments_editor][format]": 1}
        for m in marks:
            try:
                call_moodle("mod_assign_save_grade", assignmentid=item["instance"], userid=m["student"], grade=m["mark"],
                            attemptnumber=-1, addattempt=0, workflowstate="", applytoall=0, **feedback)
                results.append({**m, "error": ""})
            except RuntimeError as e:
                results.append({**m, "error": str(e)})
    else:
        from lecassist.moodle_actions import save_gradebook_marks
        grade_item = gradebook_items(course_id).get(("quiz", item["instance"]))
        if grade_item is None:
            raise RuntimeError("This quiz is not in the gradebook yet.")
        save_gradebook_marks(page, course_id, grade_item["id"], marks)
        results = [{**m, "error": ""} for m in marks]
    # eLearning can ignore a mark without an error, so check what it really stored
    now = stored_marks(course_id, item)
    emails = {s["id"]: s["email"] for s in students}
    pairs = {}
    for r in results:
        r["saved"] = not r["error"] and abs(now.get(r["student"], -1) - r["mark"]) < 0.001
        if not r["saved"] and not r["error"]:
            r["error"] = "eLearning did not keep this mark."
        if r["saved"] and r.get("cms") and emails.get(r["student"]):
            pairs[key(r["cms"])] = emails[r["student"]]
    remember(pairs)
    return results
