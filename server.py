# -*- coding: utf-8 -*-
"""
Echo English Tutor - Backend Server
====================================
改进来源：
  - Planner agent: 启动验证、健康检查、结构化错误处理
  - Architecture agent: 模块分离、知识库动态加载、清晰的数据流
  - Production Validator: 路径验证、灰度降级、全面的异常捕获
  - Verification Quality: 输入验证、配置校验、启动完整性检查
"""
import os, json, re, threading, random, pathlib, datetime
import urllib.request, urllib.error
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import uvicorn

# ═══════════════════════════════════════════
# Path Configuration (统一路径管理)
# ═══════════════════════════════════════════
APP_DIR = pathlib.Path(__file__).parent
SKILL_PATH = str(APP_DIR / "skill.md")
CONFIG_PATH = APP_DIR / "config.json"
RECORDS_PATH = APP_DIR / "data" / "records.json"
HTML_PATH = APP_DIR / "static" / "index.html"
KNOWLEDGE_DIR = APP_DIR / "knowledge"

# ═══════════════════════════════════════════
# Startup Validation (Production Validator 模式)
# ═══════════════════════════════════════════
STARTUP_ISSUES = []
STARTUP_WARNINGS = []

def validate_startup():
    """验证所有关键路径和配置，启动时报告问题。"""
    required = {
        "SKILL.md (英语教练)": SKILL_PATH,
        "Config file": str(CONFIG_PATH),
        "Frontend HTML": str(HTML_PATH),
        "Knowledge base": str(KNOWLEDGE_DIR),
        "Stage 1 knowledge": str(KNOWLEDGE_DIR / "stages" / "stage1.md"),
        "Questions stage 1": str(KNOWLEDGE_DIR / "questions" / "q_stage1.md"),
    }
    for name, path in required.items():
        if not os.path.exists(path):
            STARTUP_ISSUES.append(f"[MISS] {name}: {path}")
    
    for sub in ["stages", "questions", "reference"]:
        p = KNOWLEDGE_DIR / sub
        if not p.exists():
            STARTUP_WARNINGS.append(f"[WARN] Knowledge/{sub} dir not found: {p}")

validate_startup()

# ═══════════════════════════════════════════
# Load SKILL content
# ═══════════════════════════════════════════
SKILL_CONTENT = ""
if os.path.exists(SKILL_PATH):
    try:
        with open(SKILL_PATH, "r", encoding="utf-8") as f:
            SKILL_CONTENT = f.read()
    except Exception as e:
        STARTUP_WARNINGS.append(f"[WARN] Could not read SKILL.md: {e}")

# ═══════════════════════════════════════════
# Config & API Key (安全的配置管理)
# ═══════════════════════════════════════════
CONFIG = {}
if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            CONFIG = json.load(f)
    except:
        CONFIG = {}

API_KEY = os.environ.get("API_KEY") or CONFIG.get("api_key", "")
API_ENDPOINT = CONFIG.get("endpoint", "https://api.deepseek.com/v1/chat/completions")
AI_MODEL = CONFIG.get("model", "deepseek-chat")

# ═══════════════════════════════════════════
# Records
# ═══════════════════════════════════════════
RECORDS = {}
if os.path.exists(RECORDS_PATH):
    try:
        with open(RECORDS_PATH, "r", encoding="utf-8") as f:
            RECORDS = json.load(f)
    except:
        RECORDS = {}

# Conversation history
conv_history = []
MAX_HISTORY = 20

# ═══════════════════════════════════════════
# Knowledge Base Loader (Architecture agent 模块化模式)
# ═══════════════════════════════════════════
STAGE_INFO = {}
STAGE_QUESTIONS = {}  # {1: [parsed questions], 2: [...], ...}
REFERENCE_INFO = {}

def parse_questions(markdown_text: str) -> list:
    """
    解析题库 Markdown 格式，支持多种题型格式：
    - 标准选择: N. text (opt1/opt2/opt3) -> answer
    - 带A./B.前缀选项: N. text (A. opt1/B. opt2/C. opt3) -> answer
    - 翻译/改错(单行): N. text -> answer (跳过OK无意义答案)
    - 两步格式: N. text -> intermediate -> answer
    - 中文多行格式: N. text / A. opt1 B. opt2 / 正确答案：X
    - 单行改错: N. text -> corrected text
    """
    questions = []
    current_category = ""
    buf_q = None
    buf_opts = []
    for line in markdown_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("## "):
            current_category = line[3:].strip()
            buf_q = None
            buf_opts = []
            continue
        if line.startswith("```") or line.startswith("---"):
            continue
        if line.startswith("###"):
            buf_q = None
            buf_opts = []
            continue
        if line.startswith("#") or line.startswith("####"):
            continue
        m_ans_cn = re.search(r"正确答案[：:]\s*([A-Za-z]+)", line)
        if m_ans_cn and buf_q is not None:
            answer_letter = m_ans_cn.group(1).strip().upper()
            answer_text = ""
            for l, t in buf_opts:
                if l == answer_letter:
                    answer_text = t
                    break
            questions.append({
                "q": buf_q,
                "o": [{"l": l, "t": t} for l, t in buf_opts],
                "a": answer_letter,
                "e": f"{current_category}: 正确答案是{answer_letter}（{answer_text}）",
                "category": current_category
            })
            buf_q = None
            buf_opts = []
            continue
        if re.match(r"^(解析|Explanation)[：:]", line):
            continue
        if re.match(r"^解[：:]\s", line):
            continue
        if buf_q is not None:
            opt_parts = re.findall(
                r"([A-Za-z])[\.\)]\s*([^\\d][^A-Za-z]*(?:[A-Z][^\.\)][^A-Za-z]*)*?)(?=\s+[A-Za-z][\.\)]\s|$)", line)
            if opt_parts:
                buf_opts = [(p[0].upper(), p[1].strip()) for p in opt_parts]
                continue
        m_single_opt = re.match(r"^([A-Za-z])[\.\)]\s*(.+)", line)
        if m_single_opt and buf_q is not None:
            buf_opts.append((m_single_opt.group(1).upper(), m_single_opt.group(2).strip()))
            continue
        m_start = re.match(r"^(\d+)\.\s+(.*)", line)
        if m_start:
            buf_q = None
            buf_opts = []
            rest = m_start.group(2).strip()
            m_two = re.match(r"^(.+?)\s*->\s*(.+?)\s*->\s*(.+)$", rest)
            if m_two:
                q_text = m_two.group(1).strip()
                answer = m_two.group(3).strip()
                questions.append({
                    "q": q_text,
                    "o": [{"l": "", "t": ""}],
                    "a": answer,
                    "e": f"{current_category}: 填写 {answer}",
                    "category": current_category
                })
                continue
            m_std = re.match(r"^(.+?)\((.+?)\)\s*->\s*(.+)$", rest)
            if m_std:
                q_text = m_std.group(1).strip()
                opt_str = m_std.group(2).strip()
                answer = m_std.group(3).strip()
                if answer.upper() == "OK":
                    continue
                options = []
                letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                opt_parts = [o.strip() for o in opt_str.split("/")]
                has_prefix = bool(opt_parts) and all(
                    re.match(r"^[A-Za-z][\.\)]\s*", o) for o in opt_parts if o)
                if has_prefix:
                    for i, opt in enumerate(opt_parts):
                        clean = re.sub(r"^[A-Za-z][\.\)]\s*", "", opt).strip()
                        options.append({"l": letters[i], "t": clean})
                else:
                    for i, opt in enumerate(opt_parts):
                        options.append({"l": letters[i], "t": opt})
                answer_label = ""
                for opt in options:
                    if opt["t"].lower() == answer.lower():
                        answer_label = opt["l"]
                        break
                questions.append({
                    "q": q_text, "o": options,
                    "a": answer_label or answer,
                    "e": f"{current_category}: 正确答案是{answer_label or answer}",
                    "category": current_category
                })
                continue
            m_simple = re.match(r"^(.+?)\s*->\s*(.+)$", rest)
            if m_simple:
                q_text = m_simple.group(1).strip()
                answer = m_simple.group(2).strip()
                if answer.upper() == "OK":
                    continue
                if "___" in q_text or "＿" in q_text:
                    questions.append({
                        "q": q_text, "o": [{"l": "", "t": ""}],
                        "a": answer, "e": f"{current_category}: 填写 {answer}",
                        "category": current_category
                    })
                else:
                    questions.append({
                        "q": q_text, "o": [],
                        "a": answer, "e": f"{current_category}: 参考答案 {answer}",
                        "category": current_category,
                        "type": "translation_or_correction"
                    })
                continue
            buf_q = rest
            buf_opts = []
            continue
    return questions

def parse_writing_templates(text):
    result = {'raw': text, 'templates': [], 'opening_sentences': [], 'transition_words': []}
    section = ''
    buffer = []
    for line in text.split(chr(10)):
        if line.startswith('## '):
            if section and buffer:
                if section in ('Letter (Letter)', 'Argumentative Essay'):
                    result['templates'].append({'category': section, 'content': chr(10).join(buffer).strip()})
                elif section == 'Opening sentences':
                    result['opening_sentences'] = [l.lstrip(chr(45) + ' ').strip() for l in buffer if l.startswith(chr(45))]
                elif section == 'Transition words':
                    result['transition_words'] = [l.lstrip(chr(45) + ' ').strip() for l in buffer if l.startswith(chr(45))]
            section = line[3:].strip()
            buffer = []
        elif line.startswith('#'):
            continue
        elif section:
            buffer.append(line)
    if section and buffer:
        if section in ('Letter (Letter)', 'Argumentative Essay'):
            result['templates'].append({'category': section, 'content': chr(10).join(buffer).strip()})
        elif section == 'Opening sentences':
            result['opening_sentences'] = [l.lstrip(chr(45) + ' ').strip() for l in buffer if l.startswith(chr(45))]
        elif section == 'Transition words':
            result['transition_words'] = [l.lstrip(chr(45) + ' ').strip() for l in buffer if l.startswith(chr(45))]
    return result


def load_knowledge():
    """加载所有知识库内容到内存。"""
    # Load stage info
    for i in range(1, 6):
        sf = KNOWLEDGE_DIR / "stages" / f"stage{i}.md"
        if sf.exists():
            STAGE_INFO[str(i)] = sf.read_text(encoding="utf-8")
        else:
            STARTUP_WARNINGS.append(f"[WARN] Stage {i} file missing")
    
    # Load questions from markdown
    for i in range(1, 6):
        qf = KNOWLEDGE_DIR / "questions" / f"q_stage{i}.md"
        if qf.exists():
            parsed = parse_questions(qf.read_text(encoding="utf-8"))
            if parsed:
                STAGE_QUESTIONS[i] = parsed
    
    # Load reference materials
    for ref_file in ["writing_templates.md", "common_mistakes.md", "collocations.md"]:
        rf = KNOWLEDGE_DIR / "reference" / ref_file
        if rf.exists():
            name = ref_file.replace(".md", "")
            REFERENCE_INFO[name] = rf.read_text(encoding="utf-8")

load_knowledge()

# ═══════════════════════════════════════════
# FastAPI App
# ═══════════════════════════════════════════
app = FastAPI(title="Echo English Tutor")

class Msg(BaseModel):
    text: str
    name: str = "同学"

# ═══════════════════════════════════════════
# API: Health & Status
# ═══════════════════════════════════════════
@app.get("/api/health")
async def health_check():
    """详细的健康检查端点 (Planner agent: 状态监控模式)。"""
    return {
        "status": "error" if STARTUP_ISSUES else "ok",
        "api_configured": len(API_KEY) > 0,
        "api_endpoint": API_ENDPOINT,
        "api_model": AI_MODEL,
        "skill_loaded": len(SKILL_CONTENT) > 0,
        "skill_size": len(SKILL_CONTENT),
        "stages_loaded": len(STAGE_INFO),
        "questions_loaded": sum(len(v) for v in STAGE_QUESTIONS.values()),
        "total_questions": sum(len(v) for v in STAGE_QUESTIONS.values()),
        "startup_issues": STARTUP_ISSUES,
        "startup_warnings": STARTUP_WARNINGS,
    }

@app.get("/api/status")
async def get_status():
    return {
        "status": "ok",
        "skill_loaded": len(SKILL_CONTENT) > 0,
        "api_configured": len(API_KEY) > 0,
        "api_endpoint": API_ENDPOINT,
        "health_issues": len(STARTUP_ISSUES),
    }

# ═══════════════════════════════════════════
# API: Knowledge (Architecture agent: 数据层分离)
# ═══════════════════════════════════════════
@app.get("/api/knowledge")
async def get_knowledge():
    """暴露所有阶段信息和参考资料给前端。"""
    stages = {}
    for sid, raw_content in STAGE_INFO.items():
        lines = raw_content.strip().split("\n")
        stage_data = {
            "raw": raw_content,
            "title": "",
            "description": "",
            "grammar": [],
            "grammar_details": [],
            "vocab": "",
            "milestone": "",
            "ability": "",
        }
        in_grammar_details = False
        pending_field = None
        for line in lines:
            stripped = line.strip()
            if re.match(r"^#+\s+Stage\s", stripped):
                stage_data["title"] = re.sub(r"^#+\s+", "", stripped).strip()
                continue
            if stripped.startswith("## Description"):
                pending_field = "description"
            if stripped.startswith("## Vocabulary"):
                leftover = stripped.replace("## Vocabulary", "").strip()
                if leftover:
                    stage_data["vocab"] = leftover
                else:
                    pending_field = "vocab"
                continue
            if stripped.startswith("## Milestone"):
                leftover = stripped.replace("## Milestone", "").strip()
                if leftover:
                    stage_data["milestone"] = leftover
                else:
                    pending_field = "milestone"
                continue
            if stripped.startswith("## Grammar"):
                in_grammar_details = False
                pending_field = None
            m_ability = re.search(r"^Ability:\s*(.+)", stripped)
            if m_ability:
                stage_data["ability"] = m_ability.group(1).strip()
                continue
            m_grammar = re.search(r"^Grammar:\s*(.+)", stripped)
            if m_grammar:
                stage_data["grammar"].append(m_grammar.group(1).strip())
                continue
            m_vocab = re.search(r"^Vocabulary:\s*(.+)", stripped)
            if m_vocab:
                stage_data["vocab"] = m_vocab.group(1).strip()
                continue
            m_milestone = re.search(r"^Milestone:\s*(.+)", stripped)
            if m_milestone:
                stage_data["milestone"] = m_milestone.group(1).strip()
                continue
            if stripped.startswith("Grammar details") or stripped.startswith("Key techniques"):
                in_grammar_details = True
                continue
            if in_grammar_details and re.match(r"^\d+\.", stripped):
                stage_data["grammar_details"].append(stripped)
                continue
            if in_grammar_details and stripped.startswith("Key collocations"):
                in_grammar_details = False
                continue

            # Capture next-line content for Format 1 headings
            if pending_field:
                if pending_field == "vocab":
                    stage_data["vocab"] = stripped
                elif pending_field == "milestone":
                    stage_data["milestone"] = stripped
                elif pending_field == "description":
                    stage_data["description"] = stripped
                pending_field = None
                continue
            if re.match(r"^\d+\.", stripped) and not in_grammar_details:
                stage_data["grammar"].append(stripped)
                continue
        stages[sid] = stage_data
    references = {}
    for name, content in REFERENCE_INFO.items():
        if name == "writing_templates":
            references[name] = parse_writing_templates(content)
        else:
            references[name] = content
    question_counts = {str(k): len(v) for k, v in STAGE_QUESTIONS.items()}
    return {
        "stages": stages,
        "references": references,
        "question_counts": question_counts,
    }


@app.get("/api/config")
async def get_config():
    return {
        "api_configured": len(API_KEY) > 0,
        "endpoint": API_ENDPOINT,
        "model": AI_MODEL
    }

@app.post("/api/set_key")
async def set_key(data: dict):
    global API_KEY, CONFIG
    key = data.get("api_key", "").strip()
    if key:
        API_KEY = key
        CONFIG["api_key"] = key
        if "endpoint" in data:
            CONFIG["endpoint"] = data["endpoint"]
        if "model" in data:
            CONFIG["model"] = data["model"]
        os.makedirs(os.path.dirname(CONFIG_PATH) or ".", exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(CONFIG, f, ensure_ascii=False, indent=2)
        return {"status": "ok", "message": "API key saved"}
    return {"status": "error", "message": "Invalid API key"}

# ═══════════════════════════════════════════
# API: Chat
# ═══════════════════════════════════════════
@app.post("/api/chat")
async def chat(msg: Msg):
    global conv_history
    text = msg.text.strip()
    if not text:
        return {"reply": "想说点什么？我在听。"}
    
    if API_KEY and SKILL_CONTENT:
        reply = call_ai_api(text, msg.name)
    else:
        reply = generate_reply(text, msg.name)
    
    return {"reply": reply}

def call_ai_api(text, name):
    """调用 AI API 进行对话 (兼容 DeepSeek API)。"""
    global conv_history
    try:
        system_prompt = ("你是Echo，一个专业的英语大师，操练着完整的五阶段备考体系。\n\n"
            + SKILL_CONTENT[:35000]
            + "\n\n教学要求：\n"
            + "1. 除非学生有基础，否则始终从阶段一开始教起\n"
            + "2. 每次回复尽量提到当前是阶段几\n"
            + "3. 以中文为主教学，附英文例句和翻译\n"
            + "4. 每课不超过3个知识点\n"
            + "5. 每课必须有练习题\n"
            + "6. 错题必须指出原因和正确用法\n"
            + "7. 回答简洁，用最简单的语言解释\n"
            + "8. 学生名字叫：" + name)

        conv_history.append({"role": "user", "content": text})
        if len(conv_history) > MAX_HISTORY * 2:
            conv_history = conv_history[-MAX_HISTORY * 2:]

        messages = [{"role": "system", "content": system_prompt}] + conv_history

        total_chars = sum(len(m.get("content", "")) for m in messages)
        if total_chars > 60000:
            conv_history = conv_history[-8:]
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
        result = json.loads(resp.read().decode("utf-8"))

        if "choices" not in result:
            return "API 返回格式异常：" + json.dumps(result, ensure_ascii=False)[:200]

        reply = result["choices"][0]["message"]["content"]
        conv_history.append({"role": "assistant", "content": reply})
        return reply

    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except:
            body = str(e)
        return (f"API 调用失败 (HTTP {e.code})\n\n详情：{body}")
    except urllib.error.URLError as e:
        return f"网络错误：无法连接 {API_ENDPOINT}\n{str(e.reason)}"
    except Exception as e:
        return f"错误：{type(e).__name__}: {str(e)[:300]}"

@app.post("/api/test_ai")
async def test_ai():
    """测试 AI API 连接是否正常。"""
    if not API_KEY:
        return {"status": "error", "message": "未配置 API key"}
    try:
        test_messages = [
            {"role": "system", "content": "You are a helpful assistant. Reply in Chinese."},
            {"role": "user", "content": "Hello, say one sentence to prove you are online."}
        ]
        data = json.dumps({
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
        result = json.loads(resp.read().decode("utf-8"))
        reply = result["choices"][0]["message"]["content"]
        return {"status": "ok", "reply": reply, "model": AI_MODEL, "endpoint": API_ENDPOINT}
    except Exception as e:
        return {"status": "error", "message": f"{type(e).__name__}: {str(e)[:500]}"}

@app.post("/api/reset")
async def reset_chat():
    global conv_history
    conv_history = []
    return {"status": "ok", "message": "对话已重置"}

# ═══════════════════════════════════════════
# Local Reply Generator (fallback when no AI API)
# ═══════════════════════════════════════════
def generate_reply(text, name):
    t = text.lower()
    if re.search(r"(你好|hi|hello|嗨|哈喽|hey)", t):
        return f"你好啊，{name}！我是你的英语大师 Echo。想从哪个阶段开始学？我可以先给你做个水平测试。\n\n（注：还没配置 AI API，现在回应是本地模板。点击右上角设置按钮输入 API 密钥激活）"
    if re.search(r"(你是谁|你叫什么|echo|大师)", t):
        return "我是 Echo，你的专属英语大师。我脑子里装着专升本英语的完整五阶段体系，从零基础到考纲全词汇，一步步带你上去。想学什么随时说。"
    if re.search(r"(测试|考试|考考|测验|阶段|水平|摸底)", t):
        return handle_stage_test(text, name)
    if re.search(r"(词汇|单词|背词|记单词)", t):
        return "好的，学5个高频动词：\n\n1. **come** - 来\n2. **go** - 去\n3. **eat** - 吃\n4. **drink** - 喝\n5. **like** - 喜欢\n\n记住了吗？要不要来道题？"
    if re.search(r"(语法|时态|从句|句型|被动|语态)", t):
        return "语法你想从哪块开始？\n- **一般现在时**\n- **现在进行时**\n- **一般过去时**\n- **三大从句**\n- **被动语态**\n\n告诉我，我详细讲。"
    if re.search(r"(阅读|短文|文章|读|passage)", t):
        return "**My Day**\nEvery morning, I get up at 7 o'clock.\n\n**问题**：What time does he get up?\nA. 6  B. 7  C. 8\n\n选哪个？"
    if re.search(r"(谢谢|thank|thanks|好的|明白了|懂了)", t):
        return f"不客气，{name}！有问题随时找我。"
    if re.search(r"^(a|b|c|a\)|b\)|c\)|a\.|b\.|c\.)$", t.strip()):
        return handle_test_answer(t.strip(), name)
    has_q_bank = bool(STAGE_QUESTIONS)
    features_str = ""
    if has_q_bank:
        features_str += f"\n6. **刷题** - 从题库抽题（共{sum(len(v) for v in STAGE_QUESTIONS.values())}道）"
    return f"{name}，你想学什么？\n\n我可以帮你：\n1. **词汇** - 背单词\n2. **语法** - 时态、从句\n3. **阅读** - 短文理解\n4. **写作** - 模板训练\n5. **水平测试** - 看看你什么阶段{features_str}"

# ═══════════════════════════════════════════
# Stage Test System (本地测试)
# ═══════════════════════════════════════════
test_state = {"active": False, "stage": 1, "q_index": 0, "correct": 0, "total": 0}

def handle_stage_test(text, name):
    global test_state
    stage_match = re.search(r"阶段([一二三四五12345])", text)
    if stage_match:
        stage_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5}
        raw = stage_match.group(1)
        stage_num = stage_map.get(raw, int(raw) if raw.isdigit() else 1)
    else:
        stage_num = 1
    
    test_state["active"] = True
    test_state["stage"] = stage_num
    test_state["q_index"] = 0
    test_state["correct"] = 0
    test_state["total"] = 0
    
    return f"好的{name}，来测测阶段{'一二三四五'[stage_num-1]}！\n\nShe ___ a student.\nA. am  B. is  C. are\n\n选哪个？"

def handle_test_answer(answer, name):
    global test_state
    if not test_state["active"]:
        return "要先开始测试哦。说「测试」我出题。"
    
    test_state["total"] += 1
    user_ans = answer.strip().lower().replace(")", "").replace(".", "").strip()
    
    # Simple check for demo questions
    correct_answers = {"a": "am", "b": "is", "c": "are"}
    expected = "b"  # She ___ a student -> is
    
    is_correct = user_ans == expected
    if is_correct:
        test_state["correct"] += 1
        feedback = "答对了！"
    else:
        feedback = f"不对哦。正确答案是 B (is)。\nShe 是第三人称单数，要用 is。"
    
    test_state["q_index"] += 1
    
    if test_state["q_index"] >= 2:
        test_state["active"] = False
        score = test_state["correct"]
        total_s = test_state["total"]
        pct = int(score/total_s*100) if total_s > 0 else 0
        passed = pct >= 60
        return f"{feedback}\n\n测试结束！\n正确：{score}/{total_s}（{pct}%）\n{'恭喜通过！要进入下一阶段吗？' if passed else '还需要巩固一下。要我帮你复习吗？'}"
    
    return f"{feedback}\n\n**第2题**：They ___ my friends.\nA. is  B. am  C. are\n\n选哪个？"

# ═══════════════════════════════════════════
# Quiz System (从知识库动态加载题目)
# ═══════════════════════════════════════════
QUIZ_DATA = {"total": 0, "correct": 0, "wrong_questions": [], "current_stage": 1}
QUIZ_DATA["stage_correct"] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
QUIZ_DATA["stage_total"] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
quiz_lock = threading.Lock()
rec_lock = threading.Lock()

@app.post("/api/quiz")
async def get_quiz(data: dict = None):
    """从知识库动态获取题目，支持指定阶段。"""
    with quiz_lock:
        stage = QUIZ_DATA["current_stage"]
        if data and "stage" in data:
            stage = int(data["stage"])
            stage = max(1, min(5, stage))

        # 根据掌握度调整阶段
        t = QUIZ_DATA["stage_total"].get(stage, 0)
        c = QUIZ_DATA["stage_correct"].get(stage, 0)
        mastery = c / max(t, 1)
        if mastery < 0.3 and stage > 1:
            stage -= 1
        elif mastery > 0.8 and stage < 5:
            stage += 1
        
        # 从知识库题库取题，无则使用硬编码回退
        questions = STAGE_QUESTIONS.get(stage, [])
        if not questions:
            # Fallback to hardcoded questions
            fallback = {
                1: [{"q":"She ___ a student.","o":[{"l":"A","t":"am"},{"l":"B","t":"is"},{"l":"C","t":"are"}],"a":"B","e":"is 跟第三人称单数 She"}],
                2: [{"q":"I ___ to school every day.","o":[{"l":"A","t":"go"},{"l":"B","t":"goes"},{"l":"C","t":"went"}],"a":"A","e":"一般现在时，主语 I 用 go"}],
            }
            questions = fallback.get(stage, fallback[1])
        
        q = random.choice(questions)
        return {
            "stage": stage,
            "question": q["q"],
            "options": q.get("o", []),
            "id": q.get("q", "")[:30],
            "answer": q.get("a", ""),
            "explanation": q.get("e", ""),
            "category": q.get("category", ""),
            "total_questions": len(STAGE_QUESTIONS.get(stage, [])),
        }

@app.post("/api/log_answer")
async def log_answer(data: dict):
    stage = data.get("stage", 1)
    is_correct = data.get("correct", False)
    qid = data.get("question_id", "")
    with quiz_lock:
        QUIZ_DATA["total"] += 1
        QUIZ_DATA["stage_total"][stage] = QUIZ_DATA["stage_total"].get(stage, 0) + 1
        if is_correct:
            QUIZ_DATA["correct"] += 1
            QUIZ_DATA["stage_correct"][stage] = QUIZ_DATA["stage_correct"].get(stage, 0) + 1
        else:
            QUIZ_DATA["wrong_questions"].append({"id": qid, "stage": stage})
        try:
            with open(RECORDS_PATH, "r", encoding="utf-8") as f:
                records = json.load(f)
        except:
            records = {}
        records["quiz"] = QUIZ_DATA
        os.makedirs(os.path.dirname(RECORDS_PATH), exist_ok=True)
        with open(RECORDS_PATH, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    return {"status": "ok"}

@app.get("/api/stats")
async def get_stats():
    stage_mastery = {}
    for s in range(1, 6):
        t = QUIZ_DATA["stage_total"].get(s, 0)
        c = QUIZ_DATA["stage_correct"].get(s, 0)
        stage_mastery[str(s)] = round(c/t*100) if t > 0 else 0
    rate = round(QUIZ_DATA["correct"]/QUIZ_DATA["total"]*100) if QUIZ_DATA["total"] > 0 else 0
    return {
        "total_answers": QUIZ_DATA["total"],
        "correct_rate": rate,
        "wrong_count": len(QUIZ_DATA["wrong_questions"]),
        "current_stage": QUIZ_DATA["current_stage"],
        "stage_mastery": stage_mastery,
    }

# ═══════════════════════════════════════════
# Records
# ═══════════════════════════════════════════
@app.get("/api/records")
async def get_records():
    return JSONResponse(content=RECORDS)

@app.post("/api/save_record")
async def save_record(data: dict):
    global RECORDS
    with rec_lock:
        RECORDS.update(data)
        os.makedirs(os.path.dirname(RECORDS_PATH), exist_ok=True)
        with open(RECORDS_PATH, "w", encoding="utf-8") as f:
            json.dump(RECORDS, f, ensure_ascii=False, indent=2)
    return {"status": "saved"}

# ═══════════════════════════════════════════
# Frontend
# ═══════════════════════════════════════════
@app.get("/")
async def serve_frontend():
    if HTML_PATH.exists():
        return HTMLResponse(HTML_PATH.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Frontend not found</h1><p>Expected at: " + str(HTML_PATH) + "</p>")

# ═══════════════════════════════════════════
# Startup / Main
# ═══════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 55)
    print("  Echo 英语大师 - Web版")
    print("=" * 55)
    
    if STARTUP_ISSUES:
        print("\n  [!] 启动问题:")
        for issue in STARTUP_ISSUES:
            print(f"      {issue}")
    
    if STARTUP_WARNINGS:
        print("\n  [?] 启动警告:")
        for w in STARTUP_WARNINGS:
            print(f"      {w}")
    
    print()
    if API_KEY:
        print(f"  AI 模式: 已启用 ({AI_MODEL})")
    else:
        print("  AI 模式: 未配置 (使用本地规则)")
        print("  请在网页上输入您的 API 密钥启用真正的 AI")
    
    q_count = sum(len(v) for v in STAGE_QUESTIONS.values())
    print(f"  知识库: {len(STAGE_INFO)} 个阶段, {q_count} 道题目")
    
    print()
    print("  本机访问: http://localhost:8000")
    print("  手机访问: http://[你的电脑IP]:8000")
    print("=" * 55)
    uvicorn.run(app, host="0.0.0.0", port=8000)
