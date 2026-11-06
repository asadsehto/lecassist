from ollama import chat
import json
from datetime import datetime
from lecassist.moodle_tools import add_assignment, add_material, add_course


m = "gemma4:e2b-it-qat"
today = datetime.now().strftime("%A %Y-%m-%d")
syspromp = "You are a helpful assistant to a teacher who uses tools to get tasks done on Moodle. Today is " + today + "."
tools = {"add_assignment": add_assignment, "add_material": add_material, "add_course": add_course}
def chat_with_agent(system_prompt:str= syspromp, model:str=m):
    messages=[]
    messages.append({"role":"system", "content" : system_prompt})
    while True:
        text = input("You: ")
        if(text.lower()=="exit"):
            break

        else:
             step = 0
             messages.append({"role" : "User" , "content" : text})
             r = chat(model , messages=messages , 
                      tools=[add_assignment, add_material, add_course],
                      think=True)
             if(r.message.tool_calls is not None):
                print("model tool calls" , r.message.tool_calls)
                messages.append(r.message)

                while True:
                       if(r.message.tool_calls is None or step>=10):
                         print(f"Model: {r.message.content}")
                         break
                       else:
                        for call in r.message.tool_calls:
                         step+=1
                         f_name = tools[call.function.name]
                         result = f_name(**call.function.arguments)
                         messages.append({"role":"tool", "tool_name": call.function.name , 
                                    "content":json.dumps(result)} )
                        r = chat(model , messages=messages , 
                                 tools=[add_assignment, add_material, add_course],
                                                       think=True)
                                
                        messages.append(r.message)
                        print("model tool calls" , r.message.tool_calls)
             else:
              print(f"Model: {r.message.content}")
              messages.append(r.message)

chat_with_agent()