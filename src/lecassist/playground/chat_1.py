from ollama import chat
while True:
    text = input("Enter your message (or type 'exit' to quit): ")
    if text.lower() == 'exit':
        break
    print("Continuing...")
    response = chat(
    model = "gemma4:e2b-it-qat",
    messages = [{"role": "user", "content": text}],
    think = False
)
    print(response.message.content)