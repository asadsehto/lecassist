"""Start the eLearning API and teacher forms: uv run --env-file .env python -m lecassist.server"""
import uvicorn

if __name__ == "__main__":
    print("Teacher app: http://127.0.0.1:8100   API docs: http://127.0.0.1:8100/docs")
    uvicorn.run("lecassist.server.app:app", host="127.0.0.1", port=8100)
