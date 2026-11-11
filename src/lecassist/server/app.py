"""HTTP API for the teacher's eLearning actions.

Any UI (the simple forms in ui/teacher-app now, the desktop app later) calls
these endpoints. Open http://127.0.0.1:8100/docs for the full list.
"""
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
from lecassist.server import agent

app = FastAPI(title="LecAssist eLearning API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# One browser action at a time, so two clicks never log in twice in parallel.
browser_lock = threading.Lock()
agent_lock = threading.Lock()  # one conversation turn at a time (agent.context is shared)
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
        model_ok = agent.m in names
    except Exception:
        model_ok = False
    return {"moodle": moodle_ok, "model": agent.m.split(":")[0], "model_ok": model_ok}


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


# ---------- prompt mode ----------

UPLOAD_DIR = Path(tempfile.mkdtemp(prefix="lecassist-uploads-"))


@app.post("/api/uploads")
def upload_files(files: list[UploadFile] = File(...)):
    """Keep files for a prompt; send their ids with /api/agent/plan."""
    saved = []
    for f in files:
        if not f.filename:
            continue
        file_id = uuid.uuid4().hex
        folder = UPLOAD_DIR / file_id
        folder.mkdir()
        path = folder / Path(f.filename).name
        path.write_bytes(f.file.read())
        agent.uploads[file_id] = {"name": path.name, "path": str(path)}
        saved.append({"id": file_id, "name": path.name})
    return saved


class Message(BaseModel):
    role: str
    content: str


class PlanIn(BaseModel):
    messages: list[Message]
    task: str = "assignment"
    course_id: int | None = None
    file_ids: list[str] = []


@app.post("/api/agent/plan")
def agent_plan(body: PlanIn):
    """Turn the conversation into a plan to approve, or a question back to the teacher."""
    try:
        if body.task not in agent.tools:
            raise HTTPException(400, "task must be assignment, material or course")
        with agent_lock:
            return agent.ask_agent([m.model_dump() for m in body.messages], body.task, body.course_id, body.file_ids)
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(503, f"The assistant is not available: {e}. Check that Ollama is running.")


class RunIn(BaseModel):
    plan_id: str


@app.post("/api/agent/run")
def agent_run(body: RunIn):
    """Carry out a plan the teacher approved."""
    with browser_lock:
        try:
            result = agent.run(body.plan_id)
        except KeyError as e:
            raise HTTPException(404, str(e.args[0]))
        except RuntimeError as e:
            raise HTTPException(400, str(e))
    done = {"assignment": "Assignment created", "material": "Material uploaded", "course": "Course created"}
    return {"message": done[result["task"]], **result}


# The simple teacher forms. A different UI can ignore this and call /api directly.
UI_DIR = Path(__file__).resolve().parents[3] / "ui" / "teacher-app"
if UI_DIR.exists():
    app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")
