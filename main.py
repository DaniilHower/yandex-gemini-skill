import os
import json
import httpx
from fastapi import FastAPI, Request, Response

app = FastAPI()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

# Список моделей по приоритету
MODELS_TO_TRY = [
    "gemini-2.5-flash",
    "gemini-3.8-flash",
    "gemini-2.5-pro",
]

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
        payload_data = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": f"Ты голосовой ассистент в Яндекс Станции. Ответь кратко (1-2 предложения), четко и без Markdown-символов: {user_text}"
                        }
                    ]
                }
            ]
        }

        reply_text = None
        last_error = ""

        # Пробуем отправить запрос по очереди в доступные модели
        async with httpx.AsyncClient(timeout=15.0) as client:
            for model_name in MODELS_TO_TRY:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
                try:
                    res = await client.post(url, json=payload_data)
                    res_json = res.json()

                    if res.status_code == 200:
                        reply_text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                        break
                    else:
                        err_msg = res_json.get("error", {}).get("message", res.text)
                        last_error = f"{model_name}: {err_msg[:80]}"
                except Exception as e:
                    last_error = str(e)

        if not reply_text:
            reply_text = f"Нейросеть временно занята. Ошибка: {last_error[:100]}"

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