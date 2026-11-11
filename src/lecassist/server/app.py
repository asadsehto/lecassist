"""HTTP API for the teacher app.

The agents live in lecassist/playground (Elearning_Agent, Summary_Agent) and use
the tools in lecassist/moodle_tools.py. This file only runs them and passes the
tools' approve() questions to the app. Open http://127.0.0.1:8100/docs for the list.
"""
import re
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from lecassist import moodle_actions as moodle
from lecassist import moodle_tools
from lecassist.playground import Elearning_Agent, Summary_Agent

app = FastAPI(title="LecAssist eLearning API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# One browser action at a time, so two clicks never log in twice in parallel.
browser_lock = threading.Lock()
categories_cache: list[dict] = []


def parse_time(value: str | None, field: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(400, f"{field}: use the format YYYY-MM-DDTHH:MM")


def run_in_moodle(action, *args, **kwargs) -> dict:
    """Log in, run one moodle_actions function and turn Moodle errors into HTTP 400."""
    with browser_lock:
        try:
            with moodle.moodle_page() as page:
                return action(page, *args, **kwargs)
        except RuntimeError as e:
            raise HTTPException(400, str(e))


def save_uploads(files: list[UploadFile], folder: str) -> list[str]:
    paths = []
    for f in files:
        if not f.filename:
            continue
        path = Path(folder) / Path(f.filename).name
        path.write_bytes(f.file.read())
        paths.append(str(path))
    return paths


# ---------- lists for dropdowns ----------

@app.get("/api/status")
def get_status():
    """Whether eLearning and the local model can be reached, for the status area."""
    try:
        moodle.list_courses()
        moodle_ok = True
    except Exception:
        moodle_ok = False
    try:
        import ollama
        names = [m.model for m in ollama.list().models]
        model_ok = Elearning_Agent.m in names
    except Exception:
        model_ok = False
    return {"moodle": moodle_ok, "model": Elearning_Agent.m.split(":")[0], "model_ok": model_ok}


@app.get("/api/courses")
def get_courses():
    return moodle.list_courses()


@app.get("/api/courses/{course_id}/weeks")
def get_weeks(course_id: int):
    return moodle.list_weeks(course_id)


@app.get("/api/categories")
def get_categories():
    if not categories_cache:
        categories_cache.extend(run_in_moodle(moodle.list_categories))
    return categories_cache


# ---------- actions ----------

class CourseIn(BaseModel):
    fullname: str = Field(min_length=1)
    shortname: str = Field(min_length=1)
    category_id: int
    start: datetime
    end: datetime | None = None
    weeks: int = Field(14, ge=1, le=52)
    summary: str = ""
    visible: bool = True


@app.post("/api/courses")
def create_course(course: CourseIn):
    if course.end and course.end <= course.start:
        raise HTTPException(400, "End date must be after the start date")
    result = run_in_moodle(moodle.create_course, course.fullname.strip(), course.shortname.strip(),
                           course.category_id, course.start, course.end, course.weeks,
                           course.summary, course.visible)
    return {"message": f"Course '{course.fullname}' created", **result}


@app.post("/api/assignments")
def create_assignment(
    course_id: int = Form(...),
    section: int = Form(...),
    name: str = Form(..., min_length=1),
    due: str = Form(...),
    description: str = Form(""),
    show_description: bool = Form(False),
    allow_from: str = Form(""),
    cutoff: str = Form(""),
    online_text: bool = Form(False),
    file_submissions: bool = Form(True),
    max_files: int = Form(1, ge=1, le=20),
    max_grade: int = Form(100, ge=1, le=100),
    visible: bool = Form(True),
    notify_students: bool = Form(False),
    attachments: list[UploadFile] = File(default=[]),
):
    due_at = parse_time(due, "Due date")
    allow_at = parse_time(allow_from, "Allow submissions from")
    cutoff_at = parse_time(cutoff, "Cut-off date")
    if allow_at and allow_at >= due_at:
        raise HTTPException(400, "Due date must be after 'Allow submissions from'")
    if cutoff_at and cutoff_at < due_at:
        raise HTTPException(400, "Cut-off date cannot be earlier than the due date")
    if not (online_text or file_submissions):
        raise HTTPException(400, "Choose at least one submission type")
    with tempfile.TemporaryDirectory() as folder:
        files = save_uploads(attachments, folder)
        result = run_in_moodle(moodle.create_assignment, course_id, section, name.strip(), due_at,
                               description=description, show_description=show_description,
                               allow_from=allow_at, cutoff=cutoff_at, online_text=online_text,
                               file_submissions=file_submissions, max_files=max_files,
                               max_grade=max_grade, attachments=files, visible=visible,
                               notify_students=notify_students)
    return {"message": f"Assignment '{name}' created", **result}


@app.post("/api/materials")
def add_material(
    course_id: int = Form(...),
    section: int = Form(...),
    name: str = Form(..., min_length=1),
    description: str = Form(""),
    show_description: bool = Form(False),
    visible: bool = Form(True),
    notify_students: bool = Form(False),
    files: list[UploadFile] = File(...),
):
    with tempfile.TemporaryDirectory() as folder:
        paths = save_uploads(files, folder)
        if not paths:
            raise HTTPException(400, "Choose at least one file")
        result = run_in_moodle(moodle.add_material, course_id, section, name.strip(), paths,
                               description=description, show_description=show_description,
                               visible=visible, notify_students=notify_students)
    return {"message": f"Material '{name}' uploaded", **result}


# ---------- running the agents ----------
# An agent runs in a background "job". When one of the moodle_tools calls
# approve(), the job waits and the app shows the question with Yes/No buttons.

UPLOAD_DIR = Path(tempfile.mkdtemp(prefix="lecassist-uploads-"))
uploads: dict[str, dict] = {}   # file id -> {"name", "path"}
jobs: dict[str, dict] = {}
lectures: list[dict] = []       # recorded lectures, newest first (kept while the server runs)
current = threading.local()     # which job the current thread belongs to


class ChangeRequested(BaseException):
    """The teacher pressed Change: stop the agent so they can say what to fix.
    BaseException, so the agent loop's `except Exception` does not swallow it."""


def app_approve(action: str) -> bool:
    """Replaces moodle_tools.approve: ask in the app instead of input()."""
    job = current.job
    action = re.sub(re.escape(str(UPLOAD_DIR)) + r"/[0-9a-f]+/", "", action)  # show file names, not temp paths
    job["question"] = action
    job["answer"] = None
    job["event"].clear()
    job["event"].wait(timeout=1800)
    yes = job["answer"] is True
    change = job["answer"] == "change"
    job["approvals"].append({"action": action, "approved": yes, "change": change})
    job["question"] = None
    if change:
        raise ChangeRequested(action)
    return yes


def changed(e: ChangeRequested) -> str:
    return "Nothing was done. What should I change about: " + str(e) + "?"


moodle_tools.approve = app_approve


def start_job(work, *args) -> dict:
    job = {"id": uuid.uuid4().hex, "state": "working", "stage": "", "question": None, "answer": None,
           "approvals": [], "result": None, "error": None, "event": threading.Event()}
    jobs[job["id"]] = job

    def target():
        current.job = job
        try:
            job["result"] = work(job, *args)
            job["state"] = "done"
        except Exception as e:
            job["error"] = str(e)
            job["state"] = "error"
        except ChangeRequested as e:
            job["result"] = changed(e)
            job["state"] = "done"

    threading.Thread(target=target, daemon=True).start()
    return job


def job_view(job: dict) -> dict:
    return {k: job[k] for k in ("id", "state", "stage", "question", "approvals", "result", "error")}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "No such job")
    return job_view(jobs[job_id])


class AnswerIn(BaseModel):
    approve: bool
    change: bool = False


@app.post("/api/jobs/{job_id}/answer")
def answer_job(job_id: str, body: AnswerIn):
    """The teacher's Yes/No for the job's current question."""
    job = jobs.get(job_id)
    if job is None or job["question"] is None:
        raise HTTPException(404, "Nothing is waiting for an answer")
    job["answer"] = "change" if body.change else body.approve
    job["event"].set()
    return {"ok": True}


@app.post("/api/uploads")
def upload_files(files: list[UploadFile] = File(...)):
    """Keep files for a request; send their ids with /api/agent/ask or /api/lectures."""
    saved = []
    for f in files:
        if not f.filename:
            continue
        file_id = uuid.uuid4().hex
        folder = UPLOAD_DIR / file_id
        folder.mkdir()
        path = folder / Path(f.filename).name
        path.write_bytes(f.file.read())
        uploads[file_id] = {"name": path.name, "path": str(path)}
        saved.append({"id": file_id, "name": path.name})
    return saved


def course_name(course_id: int | None) -> str:
    for c in moodle.list_courses():
        if c["id"] == course_id:
            return c["shortname"]
    return ""


# ---------- Ask (eLearning) ----------

class Message(BaseModel):
    role: str
    content: str


class AskIn(BaseModel):
    messages: list[Message]
    task: str = "assignment"
    course_id: int | None = None
    file_ids: list[str] = []


TASK_TOOLS = {"assignment": ["add_assignment"], "material": ["add_material"], "course": ["add_course"]}


@app.post("/api/agent/ask")
def agent_ask(body: AskIn):
    """Start Elearning_Agent on the conversation; poll /api/jobs/{id} for questions and the answer."""
    if body.task not in TASK_TOOLS:
        raise HTTPException(400, "task must be assignment, material or course")
    files = [uploads[i]["path"] for i in body.file_ids if i in uploads]
    course = course_name(body.course_id) if body.task != "course" else ""

    def work(job):
        try:
            return Elearning_Agent.run_agent([m.model_dump() for m in body.messages],
                                             TASK_TOOLS[body.task], course, files)
        except ChangeRequested as e:
            return changed(e)

    return job_view(start_job(work))


# ---------- Record (lectures) ----------
# Each lecture is a conversation with the eLearning agent: the first turn is the
# summary task, later turns are the teacher's replies or an edited summary.

def lecture_turn(lecture: dict, text: str | None = None, new_summary: bool = False):
    def work(job):
        if not lecture["summary"]:
            from lecassist.audio.translate import transcribe_english
            job["stage"] = "Transcribing"
            lecture["transcript"] = transcribe_english(lecture["audio"])
            job["stage"] = "Summarising"
            lecture["summary"] = Summary_Agent.summarize(lecture["transcript"])
            new = True
        else:
            new = new_summary
        if new:
            lecture["messages"] = [{"role": "user", "content": Summary_Agent.lecture_task(
                lecture["summary"], lecture["course"], lecture["week"], lecture["paths"])}]
        else:
            if lecture["paths"]:
                text_with_files = text + "\n(Attached files: " + ", ".join(lecture["paths"]) + ")"
            else:
                text_with_files = text
            lecture["messages"].append({"role": "user", "content": text_with_files})
        job["stage"] = "Checking what eLearning needs"
        try:
            reply = Elearning_Agent.run_agent(lecture["messages"], ["add_assignment", "add_material"],
                                              lecture["course"], lecture["paths"])
        except ChangeRequested as e:
            reply = changed(e)
        lecture["messages"].append({"role": "assistant", "content": reply})
        return reply

    job = start_job(work)
    lecture["turns"].append({"text": text or ("Summary edited" if new_summary else None), "job": job["id"]})


def lecture_view(lecture: dict) -> dict:
    return {k: lecture[k] for k in ("id", "course", "week", "recorded", "files", "transcript", "summary")} | {
        "turns": [{"text": t["text"], "job": job_view(jobs[t["job"]])} for t in lecture["turns"] if t["job"] in jobs]}


def find_lecture(lecture_id: str) -> dict:
    lecture = next((x for x in lectures if x["id"] == lecture_id), None)
    if lecture is None:
        raise HTTPException(404, "No such lecture")
    if any(jobs[t["job"]]["state"] == "working" for t in lecture["turns"] if t["job"] in jobs):
        raise HTTPException(409, "LecAssist is still working on this lecture. Answer its question first.")
    return lecture


def add_files(lecture: dict, file_ids: list[str]):
    for i in file_ids:
        if i in uploads and uploads[i]["path"] not in lecture["paths"]:
            lecture["paths"].append(uploads[i]["path"])
            lecture["files"].append(uploads[i]["name"])


@app.post("/api/lectures")
def new_lecture(audio: UploadFile = File(...), course_id: int = Form(...), week: int = Form(...),
                file_ids: str = Form("")):
    """Recorded audio -> English transcript -> summary -> the eLearning agent asks to do what is needed."""
    course = course_name(course_id)
    if not course:
        raise HTTPException(400, "Choose one of your courses")
    folder = UPLOAD_DIR / uuid.uuid4().hex
    folder.mkdir()
    audio_path = folder / (Path(audio.filename or "lecture.webm").name)
    audio_path.write_bytes(audio.file.read())
    lecture = {"id": uuid.uuid4().hex, "course": course, "week": week, "audio": str(audio_path),
               "recorded": datetime.now().strftime("%a %d %b %Y, %H:%M"),
               "files": [], "paths": [], "transcript": "", "summary": "", "messages": [], "turns": []}
    add_files(lecture, [i for i in file_ids.split(",") if i])
    lectures.insert(0, lecture)
    lecture_turn(lecture)
    return lecture_view(lecture)


class ReplyIn(BaseModel):
    text: str = Field(min_length=1)
    file_ids: list[str] = []


@app.post("/api/lectures/{lecture_id}/reply")
def reply_lecture(lecture_id: str, body: ReplyIn):
    """Answer the agent's question or ask for a change; attached files are added to the lecture."""
    lecture = find_lecture(lecture_id)
    add_files(lecture, body.file_ids)
    lecture_turn(lecture, body.text.strip())
    return lecture_view(lecture)


class SummaryIn(BaseModel):
    summary: str = Field(min_length=1)


@app.post("/api/lectures/{lecture_id}/summary")
def edit_summary(lecture_id: str, body: SummaryIn):
    """Save the teacher's edited summary and let the agent check it again from the start."""
    lecture = find_lecture(lecture_id)
    lecture["summary"] = body.summary.strip()
    lecture_turn(lecture, new_summary=True)
    return lecture_view(lecture)


@app.get("/api/lectures")
def get_lectures():
    """Recorded lectures with their summaries and every agent turn."""
    return [lecture_view(lec) for lec in lectures]


@app.get("/api/lectures/{lecture_id}")
def get_lecture(lecture_id: str):
    lecture = next((x for x in lectures if x["id"] == lecture_id), None)
    if lecture is None:
        raise HTTPException(404, "No such lecture")
    return lecture_view(lecture)


# The simple teacher forms. A different UI can ignore this and call /api directly.
UI_DIR = Path(__file__).resolve().parents[3] / "ui" / "teacher-app"
if UI_DIR.exists():
    app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")
