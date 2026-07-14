def call_ai_api(text, name):
    global conv_history
    try:
        system_prompt = ("你是Echo，一个专业的英语辅导大师。以下是你的完整身份设定：\n\n"
            + SKILL_CONTENT
            + "\n\n你必须严格按照以上设定来教学。记住：\n"
            + "1. 你是耐心温柔的英语大师，擅长从零基础带起\n"
            + "2. 教学语言以中文为主，例句标注翻译\n"
            + "3. 每次教学不超过3个新知识点\n"
            + "4. 每堂课必须有练习\n"
            + "5. 错题必须讲解原因\n"
            + "6. 鼓励为主，正确率低时先鼓励再说问题\n"
            + "7. 回答问题简洁，用最简单的语言解释\n"
            + "8. 学生名字叫：" + name)

        conv_history.append({"role": "user", "content": text})
        if len(conv_history) > MAX_HISTORY * 2:
            conv_history = conv_history[-MAX_HISTORY * 2:]

        messages = [{"role": "system", "content": system_prompt}] + conv_history

        # Truncate if total too long (rough estimate: 4 chars per token)
        total_chars = sum(len(m.get("content", "")) for m in messages)
        if total_chars > 60000:  # ~15k tokens
            # Keep system prompt + last 4 exchanges
            conv_history = conv_history[-8:]  # 4 user + 4 assistant
            messages = [{"role": "system", "content": system_prompt}] + conv_history

        payload_data = json.dumps({
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
        result = json.loads(resp_bytes.decode("utf-8"))

        if "choices" not in result:
            return "API返回格式异常：" + json.dumps(result, ensure_ascii=False)[:300]

        reply = result["choices"][0]["message"]["content"]
        conv_history.append({"role": "assistant", "content": reply})
        return reply

    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
            error_detail = body[:500]
        except:
            error_detail = str(e)
        return ("API请求失败 (HTTP " + str(e.code) + ")\n\n"
                + "错误详情：" + error_detail
                + "\n\n可能的原因：\n"
                + "1. API密钥不正确\n"
                + "2. 账户余额不足\n"
                + "3. 模型名称不对\n"
                + "4. 网络连接问题\n\n"
                + "请到设置页面检查你的API密钥，或联系API提供商。")

    except urllib.error.URLError as e:
        return ("网络连接失败：无法连接到 " + API_ENDPOINT + "\n\n"
                + "错误信息：" + str(e.reason)
                + "\n\n请检查：\n"
                + "1. 网络是否正常\n"
                + "2. API地址是否正确\n"
                + "3. 是否需要代理")

    except json.JSONDecodeError as e:
        return "API返回数据格式错误，无法解析：\n" + str(e)[:200]

    except Exception as e:
        return "调用AI时出错：" + str(type(e).__name__) + ": " + str(e)[:300]
