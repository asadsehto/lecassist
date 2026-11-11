"""Ask mode for the teacher app: the same agent loop as playground/Agent_2.py.

The model calls a tool. Instead of asking approve() in the terminal, the tool
checks the details and returns a plan. The app shows the plan, and only when
the teacher approves does run() do it on eLearning.
"""
import json
import re
import uuid
from datetime import datetime, timedelta

from ollama import chat

from lecassist import moodle_actions as moodle

m = "gemma4:e2b-it-qat"

uploads = {}   # file id -> {"name", "path"}, from /api/uploads
plans = {}     # plan id -> what to run after approval
context = {"files": [], "said": ""}   # files and words of the current request


def find_course(course: str):
    """Match AI101, ai 101 or the course's full name."""
    wanted = re.sub(r"[^a-z0-9]", "", str(course).lower())
    if not wanted:
        return None
    courses = moodle.list_courses()
    for c in courses:
        if re.sub(r"[^a-z0-9]", "", c["shortname"].lower()) == wanted:
            return c
    for c in courses:
        if wanted in re.sub(r"[^a-z0-9]", "", c["fullname"].lower()):
            return c
    return None


def find_week(course_id: int, week):
    for w in moodle.list_weeks(course_id):
        if str(w["section"]) == str(week).strip():
            return w
    return None


def read_date(text: str, time: str = "23:59"):
    text = str(text).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            d = datetime.strptime(text, fmt)
            if fmt == "%Y-%m-%d":
                d = d.replace(hour=int(time[:2]), minute=int(time[3:]))
            return d
        except ValueError:
            pass
    return None


def match_weekday(d: datetime) -> datetime:
    """If the teacher said a day like "tuesday", use the coming one (small models miscount days)."""
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    said = [i for i, name in enumerate(days) if name in context["said"] or name[:3] + " " in context["said"] + " "]
    if len(said) != 1 or d.weekday() == said[0]:
        return d
    today = datetime.now()
    ahead = (said[0] - today.weekday() - 1) % 7 + 1
    return (today + timedelta(days=ahead)).replace(hour=d.hour, minute=d.minute, second=0, microsecond=0)


def make_plan(task: str, kwargs: dict, rows: list, form: dict) -> dict:
    plan_id = uuid.uuid4().hex
    plans[plan_id] = {"task": task, "kwargs": kwargs}
    return {"plan": {"type": "plan", "plan_id": plan_id, "task": task,
                     "rows": [[k, v] for k, v in rows if v], "form": form}}


# ---------- tools the model can call ----------

def add_assignment(course: str, week: int, name: str, due: str) -> dict:
    """Create an assignment in a Moodle course under a given week.

    Args:
        course: course short name, for example AI101
        week: week number, for example 3
        name: assignment name, for example Lab 4
        due: due date and time as YYYY-MM-DD HH:MM, for example 2026-11-06 23:59
    """
    c = find_course(course)
    if c is None:
        return {"error": "no course " + str(course) + ". The teacher's courses are "
                + ", ".join(x["shortname"] for x in moodle.list_courses())}
    w = find_week(c["id"], week)
    if w is None:
        return {"error": "course " + c["shortname"] + " has no week " + str(week)}
    due_date = read_date(due)
    if due_date is None:
        return {"error": "write due as YYYY-MM-DD HH:MM"}
    due_date = match_weekday(due_date)
    found = re.search(r"(\d+)\s*marks", context["said"])
    marks = min(int(found.group(1)), 100) if found else 100
    description = ""
    files = context["files"]
    kwargs = dict(course_id=c["id"], section=w["section"], name=name, due=due_date,
                  description=description, show_description=bool(description),
                  max_grade=marks, attachments=[f["path"] for f in files])
    rows = [("Course", c["shortname"] + " · " + c["fullname"]), ("Week", w["name"]), ("Title", name),
            ("Due", due_date.strftime("%a %d %b %Y, %H:%M")), ("Marks", str(marks)),
            ("Instructions", description), ("Files", ", ".join(f["name"] for f in files))]
    form = {"course_id": c["id"], "section": w["section"], "name": name,
            "due": due_date.strftime("%Y-%m-%dT%H:%M"), "description": description, "max_grade": marks}
    return make_plan("assignment", kwargs, rows, form)


def add_material(course: str, week: int, name: str) -> dict:
    """Upload the attached files as course material under a given week of a Moodle course.

    Args:
        course: course short name, for example AI101
        week: week number, for example 3
        name: name students will see, for example Week 3 slides
    """
    description = ""
    files = context["files"]
    if not files:
        return {"error": "no file is attached. Ask the teacher to attach the file with the clip button"}
    c = find_course(course)
    if c is None:
        return {"error": "no course " + str(course) + ". The teacher's courses are "
                + ", ".join(x["shortname"] for x in moodle.list_courses())}
    w = find_week(c["id"], week)
    if w is None:
        return {"error": "course " + c["shortname"] + " has no week " + str(week)}
    kwargs = dict(course_id=c["id"], section=w["section"], name=name, files=[f["path"] for f in files],
                  description=description, show_description=bool(description))
    rows = [("Course", c["shortname"] + " · " + c["fullname"]), ("Week", w["name"]), ("Title", name),
            ("Files", ", ".join(f["name"] for f in files)), ("Note", description)]
    form = {"course_id": c["id"], "section": w["section"], "name": name, "description": description}
    return make_plan("material", kwargs, rows, form)


def add_course(fullname: str, shortname: str, weeks: int = 14, start_date: str = "") -> dict:
    """Create a new Moodle course.

    Args:
        fullname: full course name, for example Machine Learning Lab
        shortname: unique short name, for example ML301
        weeks: number of weeks, 14 if not given
        start_date: start date as YYYY-MM-DD, or empty for today
    """
    if find_course(shortname) is not None:
        return {"error": "short name " + shortname + " is already used. Ask the teacher for another one"}
    start = read_date(start_date, "00:00") or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    weeks = max(1, min(int(weeks or 14), 52))
    end = start + timedelta(weeks=weeks)
    kwargs = dict(fullname=fullname, shortname=shortname, category_id=None, start=start, end=end, weeks=weeks)
    rows = [("Full name", fullname), ("Short name", shortname), ("Starts", start.strftime("%a %d %b %Y")),
            ("Ends", end.strftime("%a %d %b %Y")), ("Weeks", str(weeks))]
    form = {"fullname": fullname, "shortname": shortname, "start": start.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"), "weeks": weeks}
    return make_plan("course", kwargs, rows, form)


tools = {"assignment": add_assignment, "material": add_material, "course": add_course}


def system_prompt(task: str, course: dict | None) -> str:
    today = datetime.now()
    days = ", ".join((today + timedelta(days=i)).strftime("%A %Y-%m-%d") for i in range(1, 15))
    text = ("You are a helpful assistant to a teacher who uses tools to get tasks done on Moodle. "
            "Today is " + today.strftime("%A %Y-%m-%d") + ". The next days are: " + days + ". "
            "Call the tool with what the teacher said. Keep the teacher's names as they wrote them. "
            "If something the tool needs is missing, ask the teacher one short question.")
    if course and task != "course":
        text += (" The teacher has selected the course " + course["shortname"] + " (" + course["fullname"]
                 + "). Use it unless the teacher names a different course.")
    if context["files"]:
        text += " Attached files: " + ", ".join(f["name"] for f in context["files"]) + "."
    return text


def ask_agent(messages: list[dict], task: str, course_id: int | None, file_ids: list[str]) -> dict:
    """Same loop as Agent_2.py; stops when a tool returns a plan or the model answers."""
    context["files"] = [uploads[i] for i in file_ids if i in uploads]
    context["said"] = " ".join(x["content"] for x in messages if x["role"] == "user").lower()
    course = next((c for c in moodle.list_courses() if c["id"] == course_id), None) if course_id else None
    tool = tools[task]
    history = [{"role": x["role"], "content": x["content"]} for x in messages]
    msgs = [{"role": "system", "content": system_prompt(task, course)}] + history
    step = 0
    while step < 5:
        r = chat(m, messages=msgs, tools=[tool], think=True)
        msgs.append(r.message)
        if r.message.tool_calls is None:
            return {"type": "message", "reply": r.message.content}
        for call in r.message.tool_calls:
            step += 1
            args = dict(call.function.arguments)
            if course and task != "course" and not args.get("course"):
                args["course"] = course["shortname"]
            try:
                result = tool(**args)
            except (TypeError, ValueError) as e:
                result = {"error": str(e)}
            if "plan" in result:
                return result["plan"]
            msgs.append({"role": "tool", "tool_name": call.function.name, "content": json.dumps(result)})
    return {"type": "message", "reply": "I couldn't work that out. Write it again with the course, week and name."}


def run(plan_id: str) -> dict:
    item = plans.pop(plan_id, None)
    if item is None:
        raise KeyError("This request has expired. Send it again.")
    action = {"assignment": moodle.create_assignment, "material": moodle.add_material,
              "course": moodle.create_course}[item["task"]]
    with moodle.moodle_page() as page:
        if item["task"] == "course" and item["kwargs"]["category_id"] is None:
            item["kwargs"]["category_id"] = moodle.list_categories(page)[0]["id"]
        result = action(page, **item["kwargs"])
    return {"task": item["task"], **result}
