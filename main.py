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
        # Прямой запрос к Google Gemini REST API
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        payload_data = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": f"Ты голосовой ассистент в Яндекс Станции. Ответь кратко (1-2 предложения), четко и без Markdown-разметки: {user_text}"
                        }
                    ]
                }
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, json=payload_data)
                res_json = res.json()

                if res.status_code == 200:
                    reply_text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                else:
                    err_msg = res_json.get("error", {}).get("message", res.text)
                    print(f"Gemini API Error: {res.status_code} - {err_msg}")
                    reply_text = f"Ошибка Gemini: {err_msg[:120]}"
        except Exception as e:
            print(f"Network Error: {e}")
            reply_text = "Не удалось связаться с сервером Gemini."

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