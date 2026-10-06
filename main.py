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
        payload_data = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": f"Ты голосовой ассистент Алиса на базе Gemini. Ответь кратко (1-2 предложения), четко и без Markdown-символов (*, #): {user_text}"
                        }
                    ]
                }
            ]
        }

        reply_text = None
        last_error = ""

        async with httpx.AsyncClient(timeout=20.0) as client:
            # 1. Сначала пробуем стабильную gemini-3.8-flash
            candidate_models = ["gemini-3.8-flash"]

            # Дополнительно запрашиваем список поддерживаемых моделей у Google
            try:
                list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
                res_list = await client.get(list_url)
                if res_list.status_code == 200:
                    models_info = res_list.json().get("models", [])
                    for m in models_info:
                        m_name = m.get("name", "").replace("models/", "")
                        methods = m.get("supportedGenerationMethods", [])
                        if "generateContent" in methods and m_name not in candidate_models:
                            candidate_models.append(m_name)
            except Exception as e:
                print(f"Error fetching models: {e}")

            # 2. Пробуем модели по очереди
            for model_name in candidate_models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
                try:
                    res = await client.post(url, json=payload_data)
                    res_json = res.json()

                    if res.status_code == 200:
                        parts = res_json["candidates"][0]["content"]["parts"]
                        reply_text = parts[0]["text"].strip()
                        break
                    else:
                        err_msg = res_json.get("error", {}).get("message", res.text)
                        last_error = f"{model_name}: {err_msg[:80]}"
                except Exception as e:
                    last_error = f"{model_name}: {str(e)[:80]}"

        if not reply_text:
            reply_text = f"Не удалось получить ответ: {last_error[:100]}"

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