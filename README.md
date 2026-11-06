# LecAssist

**An AI based agent system for recording, summarising and managing university lectures.**

Final Year Project, BS Computer Science (Batch 2023), Department of Computer Science, Sukkur IBA University.
Supervisor: **Dr. Saif Hassan**

| Member | ID | Part of the system |
|---|---|---|
| Asad Saleem | 023-23-0213 | AI models and agents (eLearning portal agent, model layer, summaries, messaging) |
| Shoaib Ahmed | 023-23-0231 | Desktop application and integration of the AI with the software |
| Asghar Ali | 023-23-0218 | Audio and speech pipeline (cleaning, transcription, speaker separation, testing) |

---

## 1. What the project does

A teacher's work does not end with the lecture. Assignments announced in class have to be typed into the eLearning portal, material has to be uploaded under the right week, and notes have to reach students. LecAssist turns one lecture recording into that work:

1. **Record and clean** the classroom audio.
2. **Transcribe** mixed Urdu and English speech locally and separate the teacher's voice from the students'.
3. **Understand** the transcript: summary, key terms, assignments and deadlines.
4. **Act** on it with an AI agent: create assignments, upload material and create courses on the Moodle eLearning portal, always **after the teacher approves**.
5. **Deliver** results and take new instructions on Telegram/WhatsApp.

Everything can run **offline on the teacher's own machine** (local models through Ollama), so classroom audio does not have to leave the university network.

## 2. Progress at 30%

| Module | Status | Where |
|---|---|---|
| Local LLM access (Ollama, `gemma4:e2b-it-qat`), chat memory, structured output | Done | `src/lecassist/playground/chat_1.py`, `extract.py` |
| Tool calling and agent loop, **written from scratch (no LangChain/LangGraph)** | Done | `src/lecassist/playground/tools_1.py`, `Agent_1.py` |
| Moodle REST client: find a course and its weeks | Done | `src/lecassist/Moodle.py` |
| Browser automation (Playwright) on Moodle: login, create assignment with due date and PDF, upload material to a week, create a course | Done | `src/lecassist/browser.py` |
| Moodle agent tools + teacher approval before every action | Done | `src/lecassist/moodle_tools.py`, `playground/Agent_2.py` |
| Audio pipeline: 16 kHz mono conversion, noise reduction, faster-whisper transcription (Urdu default, code-switching prompt), pyannote speaker diarization, merge, WER scoring | Working prototype | `src/lecassist/audio/` |
| Telegram delivery and approval buttons | In progress | — |
| Desktop app (Electron/React + FastAPI), summaries, semester search, quiz generation | Not started / planned | — |

All portal automation is developed and tested **only on a local copy of Moodle** (same version as the university portal), never on the live system.

## 3. Demo video

**30% demo:** _add link here (YouTube unlisted or Google Drive)_

The video shows: the agent receiving a request in plain English, finding the course and week, asking the teacher for approval, and Playwright creating the assignment on Moodle; then the audio pipeline producing a transcript.

## 4. How it works

```
Teacher request (text now, Telegram later)
        │
        ▼
Agent loop (Agent_2.py) ── local model on Ollama with tool calling
        │  model chooses a tool and its arguments
        ▼
moodle_tools.py
   add_assignment / add_material / add_course
        │ 1. find_course + find_week   (Moodle REST API, Moodle.py)
        │ 2. approve(...)              (teacher types yes/no)
        │ 3. Playwright fills the Moodle form (browser.py)
        ▼
Result dict ──► back to the model ──► reply to the teacher
```

Why two ways of talking to Moodle: the Moodle REST API can **read** courses and weeks, but Moodle has **no web service function to create an assignment or upload a file to a week**, so creation is done by browser automation (Playwright) using the teacher's own login.

The audio pipeline (`src/lecassist/audio/main.py`) runs: convert to 16 kHz mono → optional noise reduction → faster-whisper transcription → pyannote diarization → merge into a speaker-labelled transcript → optional WER against a hand-written reference.

## 5. Project structure

```
lecassist/
├── pyproject.toml           dependencies (managed with uv)
├── .env.example             settings to copy into .env (no real values)
└── src/lecassist/
    ├── Moodle.py            Moodle REST client: call_moodle, find_course, find_week
    ├── browser.py           Playwright: login, create_assignment, upload_material, create_course
    ├── moodle_tools.py      agent tools with lookups, approval and error handling
    ├── playground/          step-by-step learning and test scripts
    │   ├── chat_1.py        first chat with the local model
    │   ├── extract.py       structured output (JSON / Pydantic)
    │   ├── tools_1.py       first tools
    │   ├── Agent_1.py       agent loop from scratch
    │   ├── Agent_2.py       Moodle agent (uses moodle_tools.py)
    │   ├── moodle_1.py      Moodle REST experiments
    │   └── pw_1.py          Playwright tests
    └── audio/               speech pipeline (see audio/README.md)
        ├── main.py, audio_prep.py, transcribe.py, diarize.py, merge.py, evaluate.py
        └── data/transcripts/ sample outputs
```

## 6. Running it

### Requirements

- Python 3.14 and [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com) with the model pulled: `ollama pull gemma4:e2b-it-qat`
- A Moodle 4.3 site to test on. We use a local Docker copy of Moodle 4.3.2+ (the same build as the university portal) at `http://localhost:8000`, with a teacher account and a REST web service token.

### Setup

```bash
git clone https://github.com/asadsehto/lecassist.git
cd lecassist
uv sync
uv run playwright install chromium
cp .env.example .env      # then fill in your Moodle URL, token and teacher login
```

### Run the Moodle agent

```bash
uv run --env-file .env src/lecassist/playground/Agent_2.py
```

Example requests:

```
Create an assignment Lab 4 in AI101 week 4 due 2026-11-13 at 23:59
Upload /path/to/slides.pdf to AI101 week 4 as Week 4 slides
Make a new course Computer Vision with short name CV501
```

### Run the audio pipeline

See [`src/lecassist/audio/README.md`](src/lecassist/audio/README.md). It needs FFmpeg and a Hugging Face token (`HF_TOKEN`) for pyannote.

## 7. Results so far

All results below are from real runs on the local Moodle copy.

**Agent with a local model (gemma4 e2b, tool calling, temperature 0):**

| Request | Tool call made by the model | Outcome |
|---|---|---|
| Create an assignment called Lab 4 in AI101 week 4, due 2026-11-13 at 23:59 | `add_assignment(course='AI101', week=4, name='Lab 4', due='2026-11-13 23:59')` | Created |
| Create Quiz 1 in DBS201 week 2 due **next Friday at 11pm**, attach a PDF (asked on Sunday 1 Nov) | `due='2026-11-06 23:00'`, `pdf_path=...` | Created with PDF; relative date resolved correctly |
| Upload a PDF to AI101 week 4 as Week 4 slides | `add_material(...)` | Uploaded (1 of 4 runs failed at login with a session timeout and was reported to the user) |
| Make a new course Computer Vision with short name CV501 | `add_course(fullname='Computer Vision', shortname='CV501', weeks=14)` | Created |
| Create assignment in course XYZ999 | `add_assignment(course='XYZ999', ...)` | Tool returned "no course with short name XYZ999"; model asked for the correct course |
| Same requests with approval answered `no` / `nah` | — | Nothing created; model reported the cancellation and did not retry |

- With the model's thinking mode on, the agent picked the correct tools in **6 of 6** test questions, against **5 of 6** with it off, but answers were about **4.7× slower**.
- Each action takes about **10–25 seconds** end to end on a MacBook Air (model + browser).
- Results were verified independently through the Moodle REST API (`core_course_get_contents`), for example `Week 3 [('assign', 'Lab 3 test'), ('assign', 'Lab 3 with PDF')]`, and the attached PDF was listed in `introattachments`.

**Moodle automation edge cases handled:**

- Moodle rejects a due date later than the default "Remind me to grade by" date; the tool turns that field off.
- Moodle's file picker redraws its upload form after it opens; uploading too early lost the file, so the tool waits for it.
- Form errors (missing name, duplicate course short name) are read from the page and returned as clear messages, e.g. `not saved: Short name is already used for another course`.

**Audio pipeline:** transcripts of two trimmed real lecture clips are in `src/lecassist/audio/data/transcripts/` (Whisper segments, speaker turns and merged transcript). Mixed Urdu/English accuracy is still low on these clips; measuring WER against hand-written references is the next step.

## 8. Next steps

- Telegram bot for requests and Yes/No approval buttons.
- Summaries, key terms and assignment/deadline extraction from transcripts, feeding the Moodle agent.
- Hand-written reference transcripts and WER reporting for the mixed-language parts.
- Desktop application and FastAPI service connecting the pipeline and the agents.
- Test on the university portal (after approval) with the right timezone (the lab currently stores times in UTC).

## 9. Security

- Moodle token, passwords and the Hugging Face token are kept in `.env`, which is not committed.
- Every outside action needs the teacher's explicit `yes`.
- Lecture audio is not stored in the repository.
