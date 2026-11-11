from ollama import chat
import json
from datetime import datetime, timedelta
from lecassist.moodle_tools import add_assignment, add_material, add_course

# The Agent_2 loop for the app: the chat comes from the app instead of input(),
# and the tools' approve() is answered with the app's Yes/No buttons.

m = "gemma4:e2b-it-qat"
tools = {"add_assignment": add_assignment, "add_material": add_material, "add_course": add_course}


def make_prompt(course: str = "", files: list = []) -> str:
    today = datetime.now()
    days = ", ".join((today + timedelta(days=i)).strftime("%A %Y-%m-%d") for i in range(1, 15))
    syspromp = ("You are a helpful assistant to a teacher who uses tools to get tasks done on Moodle. "
                "Today is " + today.strftime("%A %Y-%m-%d") + ". The next days are: " + days + ". "
                "Write due dates as YYYY-MM-DD HH:MM. "
                "If something the tool needs is missing, ask the teacher one short question.")
    if course:
        syspromp += " The teacher selected the course " + course + ". Use it unless they name another course."
    if files:
        syspromp += " Attached files, use these exact paths: " + ", ".join(files) + "."
    return syspromp


def run_agent(messages: list, tool_names: list, course: str = "", files: list = []) -> str:
    """messages is the chat so far (user and assistant turns). Returns the model's answer."""
    messages = [{"role": "system", "content": make_prompt(course, files)}] + messages
    tool_list = [tools[name] for name in tool_names]
    step = 0
    r = chat(m, messages=messages, tools=tool_list, think=True)
    messages.append(r.message)
    while r.message.tool_calls is not None and step < 10:
        for call in r.message.tool_calls:
            step += 1
            f_name = tools.get(call.function.name)
            if f_name is None:
                result = {"error": "there is no tool called " + call.function.name}
            else:
                try:
                    result = f_name(**call.function.arguments)
                except Exception as e:
                    result = {"error": str(e)}
            messages.append({"role": "tool", "tool_name": call.function.name,
                             "content": json.dumps(result)})
        r = chat(m, messages=messages, tools=tool_list, think=True)
        messages.append(r.message)
    return r.message.content
