from ollama import chat
import json
from lecassist.playground.tools_1 import list_assignments ,list_courses , list_movies

m = "gemma4:e2b-it-qat"
syspromp = "You are a helpful assistant to a teacher" \
" who uses tools to get tasks done or answer questions strictly follow the names of functions and variables as they are provided in the schema"
tools = {"list_courses": list_courses, "list_movies": list_movies,
          "list_assignments":list_assignments}

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
                      tools=[list_movies, list_courses , list_assignments],
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
                                tools=[list_movies, list_courses , list_assignments],
                                think=True) 
                        messages.append(r.message)
                        print("model tool calls" , r.message.tool_calls)
             else:
              print(f"Model: {r.message.content}")
              messages.append(r.message)

chat_with_agent()
                   
             
       


