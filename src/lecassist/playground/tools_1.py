from ollama import chat
import json
def list_movies()-> list:
    """
    return  the watchlist of movies that i will want to watch 
    """
    return ["Movie 1", "Movie 2", "Movie 3"]

def list_assingments(course_name: str) -> list:
    """
    returns the list of assignments for a given course 

    Args:
        course_name(str)): the name of the course which the assignments are to be listed
    """
    course_data = {"data science":[ "Assignment 1", "Assignment 2", "Assignment 3" ], 
                   "math": ["Assignment 4", "Assignment 5"]}
    return course_data.get(course_name, [])

def list_courses() -> list:
    """
    returns the list of courses for a given user
    """
    data = ["data science", "math"]
    return data

m = "gemma4:e2b-it-qat"
syspromp = "You are a helpful assistant to a teacher" \
" who uses tools to get tasks done or answer questions"
tools = {"list_courses": list_courses, "list_movies": list_movies,
          "list_assingments":list_assingments}

def chat_with_assistant_with_tools(sys_prompt:str = syspromp, model: str = m):
    messages = []
    messages.append({"role": "System", "content": sys_prompt})
    while True:
         
         text = input("enter your message here or type exit to quit: ")
         if(text.lower() == "exit"):
                break
         
         else:
             messages.append({"role": "user", "content": text})    
             response = chat(model, messages  = messages,
                        tools= [list_movies, list_assingments, list_courses],
                        think = False)
             
             print("Model Response: " , response.message.content, "Model tool calls: " ,
             response.message.tool_calls)

             if(response.message.tool_calls is None):
                messages.append(response.message)
                print("model: ", response.message.content)

             else:
               messages.append(response.message)
               for call in response.message.tool_calls:
                f_name = call.function.name
                Args = call.function.arguments
                function= tools[f_name]
                res = function(**Args)
                messages.append({"role": "tool", "tool_name" : f_name, "content":json.dumps(res) })
             response = chat(model, messages  = messages,
                      tools= [list_movies, list_assingments, list_courses],
                     think = False)

             print(response.message.content)
             messages.append(response.message)

    
chat_with_assistant_with_tools()  
     