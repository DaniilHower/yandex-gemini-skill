import os
import json
import httpx
from fastapi import FastAPI, Request, Response

app = FastAPI()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

@app.api_route("/", methods=["GET", "POST"])
@app.api_route("/webhook", methods=["GET", "POST"])
async def yandex_dialog_webhook(request: Request):
    if request.method == "GET":
        return Response(content='{"status":"ok"}', media_type="application/json")

    try:
        body_bytes = await request.body()
        data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception:
        data = {}

    req = data.get("request", {})
    user_text = req.get("original_utterance") or req.get("command") or ""
    user_text = user_text.strip()

    session = data.get("session", {})

    if not user_text:
        reply_text = "Джемини на связи. О чём хотите спросить?"
    else:
        # Самая быстрая легковесная модель с минимальным временем первого токена
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
        
        payload_data = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": f"Ты голосовой ассистент Алиса на базе Gemini. Ответь кратко (1 предложение, до 15 слов), без Markdown: {user_text}"
                        }
                    ]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": 45,
                "temperature": 0.5
            }
        }

        try:
            # Таймаут 2.6 сек, чтобы успеть сформировать и отправить JSON до отсечки Яндекса
            async with httpx.AsyncClient(timeout=2.6) as client:
                res = await client.post(url, json=payload_data)
                if res.status_code == 200:
                    res_json = res.json()
                    parts = res_json.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])
                    reply_text = parts[0].get("text", "").strip() or "Ответ пуст."
                else:
                    reply_text = "Нейросеть сейчас перезагружается, повторите попытку через секунду."
        except Exception as e:
            print(f"Request timeout/error: {e}")
            reply_text = "Сервер Gemini долго думает, попробуйте спросить ещё раз."

    payload = {
        "response": {
            "text": reply_text,
            "end_session": False
        },
        "session": {
            "session_id": session.get("session_id", "default_session"),
            "message_id": session.get("message_id", 0),
            "user_id": session.get("user_id", "default_user")
        },
        "version": data.get("version", "1.0")
    }

    return Response(
        content=json.dumps(payload, ensure_ascii=False),
        media_type="application/json; charset=utf-8",
        status_code=200
    )