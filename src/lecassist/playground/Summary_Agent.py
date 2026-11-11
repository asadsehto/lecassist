from ollama import chat
from lecassist.playground.Elearning_Agent import run_agent

# Lecture transcript -> summary (Aura's LECTURE_SUMMARY prompt) -> the eLearning
# agent reads the summary and calls the Moodle tools that are needed.
# Every tool call still waits for the teacher's approval.

m = "gemma4:e2b-it-qat"

SUMMARY_PROMPT = """You are a lecture summariser. Output ONLY in this exact format, no extra text:

SUMMARY:
- (max 10 bullets, academic content only, ignore greetings)

ASSIGNMENTS DETECTED: none
(or one line per task: Task / Deadline / Submit via)

EXAM NOTES: none
(or what the teacher said about exams, quizzes or important topics)

UPLOAD NEEDED: YES / NO
UPLOAD REASON: (what to upload and where)

Rules: English only, never invent info not in the transcript.
If the teacher mentions uploading slides, examples, assignments or other material,
set UPLOAD NEEDED: YES and say what should go on eLearning.

TRANSCRIPT:
{transcript}"""


def summarize(transcript: str) -> str:
    r = chat(m, messages=[{"role": "user", "content": SUMMARY_PROMPT.format(transcript=transcript[:12000])}],
             options={"temperature": 0})
    return r.message.content.strip()


def lecture_task(summary: str, course: str, week: int, files: list = []) -> str:
    """The message the eLearning agent gets for one lecture."""
    task = ("This is the summary of my lecture for course " + course + ", week " + str(week) + ":\n\n"
            + summary + "\n\n"
            "Do what this lecture needs on eLearning:\n"
            "- For every assignment under ASSIGNMENTS DETECTED that has a deadline, call add_assignment "
            "in course " + course + " week " + str(week) + ".\n")
    if files:
        task += ("- UPLOAD NEEDED: upload the attached files with add_material in course " + course
                 + " week " + str(week) + ", with a short name that says what they are.\n")
    else:
        task += "- No files are attached, so do not upload anything; the teacher can attach files later.\n"
    task += ("If a deadline is not clear, ask me for the date and time. "
             "If nothing needs doing, say so. When you are done, list what you did.")
    return task


def act_on_summary(summary: str, course: str, week: int, files: list = []) -> str:
    """Let the eLearning agent do what the summary asks for, in this course and week."""
    return run_agent([{"role": "user", "content": lecture_task(summary, course, week, files)}],
                     ["add_assignment", "add_material"], course, files)
