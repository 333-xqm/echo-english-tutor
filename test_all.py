#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Echo English Tutor - Comprehensive API & Frontend Test Suite
"""
import json, sys, traceback, urllib.request, urllib.error

BASE = "http://localhost:8000"
passed = []
failed = []

def test(name, method, path, body=None, expected_status=None, check_fields=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    try:
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method=method
        )
        resp = urllib.request.urlopen(req, timeout=10)
        status = resp.status
        raw = resp.read().decode("utf-8")
        j = json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read().decode("utf-8", errors="replace")
        try: j = json.loads(raw)
        except: j = {}
    except Exception as e:
        return fail(name, f"Connection error: {e}")

    issues = []
    if expected_status is not None and status != expected_status:
        issues.append(f"expected status {expected_status}, got {status}")
    if check_fields and not j:
        issues.append(f"response not JSON")
    if check_fields:
        for field in check_fields:
            if field not in j:
                issues.append(f"missing field '{field}'")
    if issues:
        return fail(name, "; ".join(issues) + f" | raw={raw[:200]}")
    return pass_(name, f"HTTP {status} | keys={list(j.keys())[:10]}")

def pass_(name, detail):
    passed.append(f"[PASS] {name}: {detail}")
    print(f"  ✓ {name}")
    return True

def fail(name, detail):
    failed.append(f"[FAIL] {name}: {detail}")
    print(f"  ✗ {name}: {detail}")
    return False

def section(title):
    print(f"\n{'='*55}\n  {title}\n{'='*55}")

# ─────────────────────────────────────────────
section("1. Health & Status")

test("GET /api/health", "GET", "/api/health",
     expected_status=200,
     check_fields=["status","api_configured","stages_loaded","questions_loaded"])

test("GET /api/status", "GET", "/api/status",
     expected_status=200,
     check_fields=["status","skill_loaded","api_configured"])

# ─────────────────────────────────────────────
section("2. Knowledge Base")

test("GET /api/knowledge", "GET", "/api/knowledge",
     expected_status=200,
     check_fields=["stages","references","question_counts"])

# ─────────────────────────────────────────────
section("3. API Config")

test("GET /api/config", "GET", "/api/config",
     expected_status=200,
     check_fields=["api_configured","endpoint","model"])

# ─────────────────────────────────────────────
section("4. Quiz System")

test("POST /api/quiz (default)", "POST", "/api/quiz",
     body={}, expected_status=200,
     check_fields=["stage","question","options","answer","explanation"])

test("POST /api/quiz (stage=1)", "POST", "/api/quiz",
     body={"stage":1}, expected_status=200,
     check_fields=["stage","question","options","answer"])

test("POST /api/quiz (stage=2)", "POST", "/api/quiz",
     body={"stage":2}, expected_status=200,
     check_fields=["stage","question","options","answer"])

test("POST /api/quiz (stage=3)", "POST", "/api/quiz",
     body={"stage":3}, expected_status=200,
     check_fields=["stage","question","options","answer"])

test("POST /api/quiz (stage=4)", "POST", "/api/quiz",
     body={"stage":4}, expected_status=200,
     check_fields=["stage","question","options","answer"])

test("POST /api/quiz (stage=5)", "POST", "/api/quiz",
     body={"stage":5}, expected_status=200,
     check_fields=["stage","question","options","answer"])

# ─────────────────────────────────────────────
section("5. Log Answer")

test("POST /api/log_answer (correct)", "POST", "/api/log_answer",
     body={"stage":1,"correct":True,"question_id":"test_q1"},
     expected_status=200, check_fields=["status"])

test("POST /api/log_answer (wrong)", "POST", "/api/log_answer",
     body={"stage":2,"correct":False,"question_id":"test_q2"},
     expected_status=200, check_fields=["status"])

# ─────────────────────────────────────────────
section("6. Statistics")

test("GET /api/stats", "GET", "/api/stats",
     expected_status=200,
     check_fields=["total_answers","correct_rate","wrong_count","current_stage","stage_mastery"])

# ─────────────────────────────────────────────
section("7. Chat (local mode, no AI key)")

test("POST /api/chat (greeting)", "POST", "/api/chat",
     body={"text":"你好","name":"测试同学"},
     expected_status=200, check_fields=["reply"])

test("POST /api/chat (vocab)", "POST", "/api/chat",
     body={"text":"我想学单词","name":"测试同学"},
     expected_status=200, check_fields=["reply"])

test("POST /api/chat (grammar)", "POST", "/api/chat",
     body={"text":"语法","name":"测试同学"},
     expected_status=200, check_fields=["reply"])

test("POST /api/chat (empty)", "POST", "/api/chat",
     body={"text":"","name":"测试同学"},
     expected_status=200, check_fields=["reply"])

test("POST /api/chat (test/quiz)", "POST", "/api/chat",
     body={"text":"测试","name":"测试同学"},
     expected_status=200, check_fields=["reply"])

# ─────────────────────────────────────────────
section("8. Quiz stage validation (multiple calls)")

def verify_quiz_stage(stage):
    stages_seen = set()
    for i in range(5):
        try:
            data = json.dumps({"stage": stage}).encode("utf-8")
            req = urllib.request.Request(
                f"{BASE}/api/quiz", data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            resp = urllib.request.urlopen(req, timeout=10)
            j = json.loads(resp.read().decode("utf-8"))
            stages_seen.add(j.get("stage"))
        except Exception as e:
            fail(f"Quiz stage {stage} call #{i} failed", str(e)[:100])
    if stages_seen and min(stages_seen) <= stage <= max(stages_seen):
        pass_(f"Quiz stage {stage} returns valid stage range", f"stages_seen={stages_seen}")
    else:
        fail(f"Quiz stage {stage} unexpected stages", f"seen={stages_seen}")

for s in [1,2,3,4,5]:
    verify_quiz_stage(s)

# ─────────────────────────────────────────────
section("9. Records API")

test("GET /api/records", "GET", "/api/records",
     expected_status=200)

test("POST /api/save_record", "POST", "/api/save_record",
     body={"test_note":"hello"}, expected_status=200,
     check_fields=["status"])

# ─────────────────────────────────────────────
section("10. Records & Chat Reset API")

test("POST /api/reset", "POST", "/api/reset",
     body={}, expected_status=200,
     check_fields=["status","message"])

# ─────────────────────────────────────────────
section("11. Frontend HTML")

try:
    req = urllib.request.Request(f"{BASE}/")
    resp = urllib.request.urlopen(req, timeout=10)
    html = resp.read().decode("utf-8")
    if "<html" in html.lower() and "Echo" in html:
        pass_("Frontend returns valid HTML", f"size={len(html)}b, has Echo title")
    else:
        fail("Frontend missing expected content", f"got {len(html)}b, Echo not found")
except Exception as e:
    fail("Frontend endpoint", str(e)[:100])

# ─────────────────────────────────────────────
section("12. Error Handling")

test("POST /api/quiz (stage=99)", "POST", "/api/quiz",
     body={"stage":99}, expected_status=200,
     check_fields=["stage","question"])

test("POST /api/log_answer (empty)", "POST", "/api/log_answer",
     body={}, expected_status=200,
     check_fields=["status"])

test("POST /api/chat (no name)", "POST", "/api/chat",
     body={"text":"hello"}, expected_status=200,
     check_fields=["reply"])

# ─────────────────────────────────────────────
section("13. AI Test API (expect error since API key may be configured but not valid)")
test("POST /api/test_ai", "POST", "/api/test_ai",
     expected_status=200, check_fields=["status"])

# ─────────────────────────────────────────────
section("14. Set Key API")

test("POST /api/set_key (empty key)", "POST", "/api/set_key",
     body={"api_key":""}, expected_status=200,
     check_fields=["status","message"])

# ─────────────────────────────────────────────
section("\n=== TEST SUMMARY ===")
print(f"  Passed: {len(passed)}")
print(f"  Failed: {len(failed)}")
if failed:
    print("\n  --- FAILURES ---")
    for f in failed:
        print(f"  {f}")

with open("test_report.json", "w", encoding="utf-8") as f:
    json.dump({"passed": passed, "failed": failed,
               "passed_count": len(passed), "failed_count": len(failed)}, f,
              ensure_ascii=False, indent=2)

sys.exit(0 if not failed else 1)
