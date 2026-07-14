import urllib.error
import json as _json

def call_ai_api(text, name):
    global conv_history
    try:
        system_prompt = ("You are Echo, an English tutor. System prompt:\n\n"
            + SKILL_CONTENT[:8000]
            + "\n\nTeach in Chinese. Student name: " + name)

        conv_history.append({"role": "user", "content": text})
        if len(conv_history) > MAX_HISTORY * 2:
            conv_history = conv_history[-MAX_HISTORY * 2:]

        messages = [{"role": "system", "content": system_prompt}] + conv_history

        total_chars = sum(len(m.get("content", "")) for m in messages)
        if total_chars > 60000:
            conv_history = conv_history[-8:]
            messages = [{"role": "system", "content": system_prompt}] + conv_history

        payload_data = _json.dumps({
            "model": AI_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024,
            "stream": False
        }).encode("utf-8")

        req = urllib.request.Request(
            API_ENDPOINT,
            data=payload_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + API_KEY
            },
            method="POST"
        )

        resp = urllib.request.urlopen(req, timeout=60)
        resp_bytes = resp.read()
        result = _json.loads(resp_bytes.decode("utf-8"))

        if "choices" not in result:
            error_text = _json.dumps(result, ensure_ascii=False)[:300]
            return "API returned unexpected format: " + error_text

        reply = result["choices"][0]["message"]["content"]
        conv_history.append({"role": "assistant", "content": reply})
        return reply

    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except:
            body = str(e)
        return ("API call failed (HTTP " + str(e.code) + ")\n\nDetails: " + body
            + "\n\nPossible issues:\n1. Wrong API key\n2. Insufficient balance\n3. Wrong model name\n4. Network issue\n\nCheck your API settings.")

    except urllib.error.URLError as e:
        return "Network error: cannot reach " + API_ENDPOINT + "\n" + str(e.reason)

    except Exception as e:
        return "Error: " + str(type(e).__name__) + ": " + str(e)[:300]
