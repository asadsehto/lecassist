from ollama import chat 

response = chat(
     model ="gemma4:e2b-it-qat" ,
    messages =  [{"role" : "user", "content" : "describe who you are and your capabilities"}],
    think = False,
)

res = response.message.content
print(res)