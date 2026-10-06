import os
from fastapi import FastAPI, Request
from google import genai

app = FastAPI()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

@app.post("/webhook")
async def yandex_dialog_webhook(request: Request):
    data = await request.json()
    
    user_text = data.get("request", {}).get("command", "").strip()
    session = data.get("session", {})
    version = data.get("version", "1.0")

    if not user_text:
        return {
            "version": version,
            "session": session,
            "response": {
                "text": "Джемини слушает. О чём хотите спросить?",
                "end_session": False
            }
        }

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_text,
        )
        reply_text = response.text
    except Exception as e:
        reply_text = "Произошла ошибка при обращении к нейросети."

    return {
        "version": version,
        "session": session,
        "response": {
            "text": reply_text,
            "end_session": False
        }
    }