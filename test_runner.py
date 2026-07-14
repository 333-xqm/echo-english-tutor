#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, sys, urllib.request, urllib.error

BASE = "http://localhost:8000"
passed = []
failed = []

def test(name, method, path, body=None, check_keys=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    ok = True
    try:
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method=method
        )
        resp = urllib.request.urlopen(req, timeout=10)
        raw = resp.read().decode("utf-8")
        j = json.loads(raw) if raw else {}
        status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try: j = json.loads(raw)
        except: j = {}
        status = e.code
        ok = False
    except Exception as e:
        failed.append(f"FAIL {name}: connection error - {e}")
        return

    missing = []
    if check_keys:
        for k in check_keys:
            if k not in j:
                missing.append(k)
    if missing:
        failed.append(f"FAIL {name}: HTTP {status}, missing keys: {missing}")
    elif not ok:
        failed.append(f"FAIL {name}: HTTP {status}")
    else:
        passed.append(f"PASS {name}: HTTP {status}")

print("=" * 55)
print("  Echo English Tutor - Test Suite")
print("=" * 55)

# 1. Health & Status
test("GET /api/health","GET","/api/health",check_keys=["status","api_configured","questions_loaded","stages_loaded"])
test("GET /api/status","GET","/api/status",check_keys=["status","skill_loaded","api_configured"])

# 2. Knowledge
test("GET /api/knowledge","GET","/api/knowledge",check_keys=["stages","references","question_counts"])

# 3. Config
test("GET /api/config","GET","/api/config",check_keys=["api_configured","endpoint","model"])

# 4. Quiz - default and all stages
for stage in [None, 1, 2, 3, 4, 5]:
    label = f"POST /api/quiz (stage={stage})" if stage else "POST /api/quiz (default)"
    body = {"stage": stage} if stage else {}
    test(label, "POST", "/api/quiz", body=body, check_keys=["stage","question","options","answer"])

# 5. Log answer
test("POST /api/log_answer (correct)","POST","/api/log_answer",body={"stage":1,"correct":True,"question_id":"test1"},check_keys=["status"])
test("POST /api/log_answer (wrong)","POST","/api/log_answer",body={"stage":2,"correct":False,"question_id":"test2"},check_keys=["status"])

# 6. Stats
test("GET /api/stats","GET","/api/stats",check_keys=["total_answers","correct_rate","stage_mastery"])

# 7. Chat endpoints
for label, txt in [("greeting","你好"),("vocab","我想学单词"),("grammar","语法"),("empty",""),("test","测试")]:
    test(f"POST /api/chat ({label})","POST","/api/chat",body={"text":txt,"name":"测试"},check_keys=["reply"])

# 8. Records
test("GET /api/records","GET","/api/records")
test("POST /api/save_record","POST","/api/save_record",body={"note":"test"},check_keys=["status"])

# 9. Reset
test("POST /api/reset","POST","/api/reset",body={},check_keys=["status","message"])

# 10. Frontend HTML
try:
    req = urllib.request.Request(f"{BASE}/")
    resp = urllib.request.urlopen(req, timeout=10)
    html = resp.read().decode("utf-8")
    if "<html" in html.lower() and "Echo" in html:
        passed.append("PASS Frontend HTML: returns valid HTML with Echo title")
    else:
        failed.append("FAIL Frontend HTML: missing expected content")
except Exception as e:
    failed.append(f"FAIL Frontend HTML: {e}")

# 11. Error handling - invalid stage
test("POST /api/quiz (stage=99)","POST","/api/quiz",body={"stage":99},check_keys=["stage","question"])
test("POST /api/log_answer (empty)","POST","/api/log_answer",body={},check_keys=["status"])

# 12. AI Test (expect it to either work or return an error status)
test("POST /api/test_ai","POST","/api/test_ai",check_keys=["status"])

# 13. Set key
test("POST /api/set_key (empty)","POST","/api/set_key",body={"api_key":""},check_keys=["status","message"])

# 14. Repeat quiz for each stage 5 times to verify stage consistency
for stage in [1,2,3,4,5]:
    stages_seen = set()
    all_ok = True
    for i in range(5):
        try:
            data = json.dumps({"stage": stage}).encode("utf-8")
            req = urllib.request.Request(f"{BASE}/api/quiz", data=data, headers={"Content-Type":"application/json"}, method="POST")
            resp = urllib.request.urlopen(req, timeout=10)
            j = json.loads(resp.read().decode("utf-8"))
            stages_seen.add(j.get("stage"))
        except Exception as e:
            all_ok = False
            failed.append(f"FAIL Quiz stage {stage} call #{i}: {str(e)[:80]}")
    if all_ok and min(stages_seen) <= stage <= max(stages_seen):
        passed.append(f"PASS Quiz stage {stage} x5: stages seen = {sorted(stages_seen)}")
    elif all_ok:
        failed.append(f"FAIL Quiz stage {stage} x5: unexpected stages = {sorted(stages_seen)}")

# Summary
print()
print("=" * 55)
print(f"  Total: {len(passed)+len(failed)}  |  PASS: {len(passed)}  |  FAIL: {len(failed)}")
print("=" * 55)
if failed:
    print()
    for f in failed:
        print(f"  {f}")

result = {"passed": passed, "failed": failed, "passed_count": len(passed), "failed_count": len(failed)}
with open(r"D:\22222\英语网站\english-tutor-app\test_report.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

sys.exit(0 if not failed else 1)
