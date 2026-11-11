# Teacher app: eLearning section

The eLearning part of the LecAssist teacher app. A teacher can:

- **Ask**: pick a task (create assignment, upload material, create course), optionally choose the course, read the hints on what to include, type the request, check the plan LecAssist shows and approve it. Each task keeps its own chat.
- **Fill a form**: the same three tasks with every field, for teachers who prefer forms. "Edit in form" moves a plan from Ask into the form.

The sidebar teases the sections that come next (lectures, summaries, marks, messaging, search, quizzes); they show a "Coming soon" page.

```
ui/teacher-app/                  this UI (HTML, CSS, JS, no build step)
src/lecassist/server/app.py      the API it calls (FastAPI)
src/lecassist/server/agent.py    Ask mode: the Agent_2 loop (tool calling, think=True); tools return a plan to approve
src/lecassist/moodle_actions.py  fills Moodle's forms with Playwright
```

The UI only calls the API, so the desktop app can replace it and keep everything else.

## Run

From the repo root, with the Moodle lab and Ollama running and `.env` filled in:

```bash
uv run --env-file .env python -m lecassist.server
```

- App: http://127.0.0.1:8100
- API docs: http://127.0.0.1:8100/docs

The model is `gemma4:e2b-it-qat` (the `m` variable in agent.py). Reading a request takes about 5–15 seconds; doing it on eLearning about 5–15 seconds.

## API

Errors come back as HTTP 400 with `{"detail": "message"}`, using Moodle's own message where there is one.

### Ask mode

1. `POST /api/uploads` (multipart, field `files`, repeatable) → `[{"id", "name"}]`. Do this first when the teacher attached files.
2. `POST /api/agent/plan` (JSON) with the conversation so far:

   ```json
   {"messages": [{"role": "user", "content": "Create Lab 7 in UIT102"},
                 {"role": "assistant", "content": "Which week of UIT102 should this go in?"},
                 {"role": "user", "content": "week 4, due next Friday at 5pm, 15 marks"}],
    "task": "assignment", "course_id": 16, "file_ids": []}
   ```

   `task` is `assignment`, `material` or `course`. `course_id` is the course the teacher chose in the app, or `null`; the agent uses it unless the request names another course. The answer is either a question:

   ```json
   {"type": "message", "reply": "Which week of UIT102 should this go in?"}
   ```

   or a plan to show the teacher. Nothing has been done yet:

   ```json
   {"type": "plan", "plan_id": "…", "task": "assignment",
    "rows": [["Course", "UIT102 · UI Test Course"], ["Week", "Topic 4"], ["Title", "Lab 7"],
             ["Due", "Fri 20 Nov 2026, 17:00"], ["Marks", "15"]],
    "form": {"course_id": 14, "section": 4, "name": "Lab 7", "due": "2026-11-20T17:00", "max_grade": 15}}
   ```

   `form` holds the same values in the form's field names, for "Edit in form".
3. `POST /api/agent/run` with `{"plan_id": "…"}` after the teacher approves → `{"message", "task", "url", …}`. A plan runs once; sending it again returns 404.

### Lists for dropdowns

| Method | Path | Returns |
|---|---|---|
| GET | `/api/status` | `{"moodle": true, "model": "gemma4", "model_ok": true}` |
| GET | `/api/courses` | `[{"id", "shortname", "fullname"}]`, the teacher's courses |
| GET | `/api/courses/{id}/weeks` | `[{"section", "name"}]` |
| GET | `/api/categories` | `[{"id", "name"}]`, categories the teacher may create courses in |

### Form mode

`POST /api/courses` (JSON): `fullname`*, `shortname`*, `category_id`*, `start`* (`YYYY-MM-DDTHH:MM`), `end`, `weeks` (1–52), `summary`, `visible`.

`POST /api/assignments` (multipart): `course_id`*, `section`*, `name`*, `due`*, `description`, `show_description`, `allow_from`, `cutoff`, `file_submissions`, `online_text`, `max_files` (1–20), `max_grade` (1–100), `visible`, `notify_students`, `attachments` (files).

`POST /api/materials` (multipart): `course_id`*, `section`*, `name`*, `files`* (files), `description`, `show_description`, `visible`, `notify_students`.

Each returns `{"message", "url", …}`.

## Notes

- Dates use the teacher's Moodle timezone (the local lab uses UTC).
- Approving a plan, or confirming a form, is the teacher's approval. Nothing changes on eLearning before that.
