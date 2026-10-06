import os
from fastapi import FastAPI, Request
from google import genai

app = FastAPI()

# Инициализируем клиент Gemini
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

@app.post("/webhook")
async def yandex_dialog_webhook(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}

    req = data.get("request", {})
    user_text = req.get("original_utterance") or req.get("command") or ""
    user_text = user_text.strip()

    session = data.get("session", {})
    session_id = session.get("session_id", "")
    message_id = session.get("message_id", 0)
    user_id = session.get("user_id", "")

    # Если это первый вход в навык (команды ещё нет)
    if not user_text:
        return {
            "response": {
                "text": "Джемини на связи. О чём хотите спросить?",
                "end_session": False
            },
            "session": {
                "session_id": session_id,
                "message_id": message_id,
                "user_id": user_id
            },
            "version": data.get("version", "1.0")
        }

    # Запрос к модели Gemini
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_text,
        )
        reply_text = response.text or "Ответ пуст."
    except Exception as e:
        reply_text = "Произошла ошибка при обращении к нейросети."

    return {
        "response": {
            "text": reply_text,
            "end_session": False
        },
        "session": {
            "session_id": session_id,
            "message_id": message_id,
            "user_id": user_id
        },
        "version": data.get("version", "1.0")
    }