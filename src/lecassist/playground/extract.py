from pydantic import BaseModel , Field
from datetime import date, datetime
from ollama import chat
import pprint
from lecassist.playground.chat_1 import chat_with_assistant
class Assignment(BaseModel): 
    title:str = Field(..., description="Title of the assignment")
    course:str = Field(..., description="Course name of the assignment")
    due_date:datetime = Field(..., description="Due date of the assignment")
    description:str| None = Field(..., max_length=100, description="Description of the assignment")

pprint.pprint(Assignment.model_json_schema())
messages = []
date = datetime.now().strftime("%Y-%m-%d")
M = "gemma4:e2b-it-qat"


def chat_with_assistant(system_prompt: str = f"You extract details from assignment and create an Assignment object for the date {date}.", model: str = M):
    messages.append({"role": "System", "content": system_prompt})
    while True:
     text = input("Enter your message (or type 'exit' to quit): ")
     if text.lower() == 'exit':
        break
     print("Model Responding...")
     messages.append({"role": "User", "content": text})
     response = chat(format = Assignment.model_json_schema(), model = M, messages  = messages, 
     think = False
)
     messages.append({"role": "Assistant", "content": response.message.content})
     print(Assignment.model_validate_json(response.message.content))
     print("--------------------------------------------------")
chat_with_assistant()