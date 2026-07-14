@app.post("/api/test_ai")
async def test_ai():
    if not API_KEY:
        return {"status": "error", "message": "No API key configured"}
    try:
        import json as _json
        test_messages = [
            {"role": "system", "content": "You are a helpful assistant. Reply in Chinese."},
            {"role": "user", "content": "Hello, say one sentence to prove you are online."}
        ]
        data = _json.dumps({
            "model": AI_MODEL,
            "messages": test_messages,
            "temperature": 0.7,
            "max_tokens": 100
        }).encode("utf-8")
        req = urllib.request.Request(
            API_ENDPOINT, data=data,
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + API_KEY},
            method="POST"
        )
        resp = urllib.request.urlopen(req, timeout=30)
        result = _json.loads(resp.read().decode("utf-8"))
        reply = result["choices"][0]["message"]["content"]
        return {"status": "ok", "reply": reply, "model": AI_MODEL, "endpoint": API_ENDPOINT}
    except Exception as e:
        return {"status": "error", "message": str(type(e).__name__) + ": " + str(e)[:500]}
