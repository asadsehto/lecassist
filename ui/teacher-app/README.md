# Teacher app

The LecAssist teacher app. Sidebar:

- **Record lecture**: choose the course and week, record (pause and resume work) or upload a recording, and optionally add the slides. LecAssist writes an English transcript and a summary, then asks you to approve what eLearning needs, such as an assignment you announced or uploading the slides.
- **eLearning**
  - **From lectures**: every recorded lecture with its summary, transcript and the actions waiting for your approval.
  - **Ask**: pick a task (create assignment, upload material, create course), optionally choose the course, type the request and approve what the agent wants to do. Each task keeps its own chat.
  - **Fill a form**: the same three tasks with every field.
- **Coming next**: marks, Telegram and WhatsApp, semester search, quizzes ("Coming soon" pages).

## Where the code is

```
ui/teacher-app/                            this UI (HTML, CSS, JS, no build step)
src/lecassist/server/app.py                the API; runs the agents and passes approve() to the app
src/lecassist/playground/Elearning_Agent.py   the Agent_2 loop, used by Ask
src/lecassist/playground/Summary_Agent.py     lecture summary, then the eLearning agent acts on it
src/lecassist/moodle_tools.py              the tools both agents call (add_assignment, add_material, add_course)
src/lecassist/audio/translate.py           English transcript with faster-whisper (from Aura)
src/lecassist/moodle_actions.py            all-fields Moodle forms, used by Fill a form only
```

The agents never act on their own: every tool in `moodle_tools.py` calls `approve()`. In the terminal that is `input()`; in the app, `server/app.py` replaces it so the question shows with Approve and Decline buttons.

## Run

From the repo root, with the Moodle lab and Ollama running and `.env` filled in:

```bash
uv run --env-file .env python -m lecassist.server
```

- App: http://127.0.0.1:8100
- API docs: http://127.0.0.1:8100/docs

The first lecture downloads the Whisper "small" model. Recorded lectures are kept while the server runs.

## API

An agent runs as a **job**. Poll `GET /api/jobs/{id}`:

```json
{"id": "…", "state": "working", "stage": "Summarising",
 "question": "create assignment 'Quiz 4' in UIT102 Topic 6, due 2026-11-16 17:00",
 "approvals": [], "result": null, "error": null}
```

- `state` is `working`, `done` or `error`. `result` is the agent's last answer.
- When `question` is set, the agent is waiting. Answer with `POST /api/jobs/{id}/answer` and `{"approve": true}` or `false`.
- `approvals` lists every question already answered.

| Method | Path | Body | Starts |
|---|---|---|---|
| POST | `/api/uploads` | multipart `files` (repeat) | returns `[{"id", "name"}]` |
| POST | `/api/lectures` | multipart `audio`, `course_id`, `week`, `file_ids` (comma separated) | transcribe, summarise, act; returns `{"lecture", "job"}` |
| GET | `/api/lectures` | | lectures with summary, transcript and job |
| POST | `/api/agent/ask` | JSON `{"messages": [{"role", "content"}], "task": "assignment", "course_id": 14, "file_ids": []}` | Elearning_Agent; returns the job |
| GET | `/api/status` | | `{"moodle", "model", "model_ok"}` |
| GET | `/api/courses`, `/api/courses/{id}/weeks`, `/api/categories` | | lists for dropdowns |
| POST | `/api/courses` (JSON), `/api/assignments`, `/api/materials` (multipart) | | Fill a form, all fields |

Errors come back as HTTP 400 with `{"detail": "message"}`.
