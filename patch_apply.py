f = open("D:/11111/english-tutor-app/call_ai_replacement.py", "r", encoding="utf-8")
replacement = f.read()
f.close()

f = open("D:/11111/english-tutor-app/test_endpoint.py", "r", encoding="utf-8")
test_code = f.read()
f.close()

f = open("D:/11111/english-tutor-app/server.py", "r", encoding="utf-8")
content = f.read()
f.close()

old_start = content.find("def call_ai_api")
old_end = content.find("def generate_reply")

if old_start >= 0 and old_end >= 0:
    new_content = content[:old_start] + replacement + "\n\n" + content[old_end:]
    main_pos = new_content.find('if __name__ == "__main__":')
    if main_pos >= 0:
        new_content = new_content[:main_pos] + test_code + "\n\n\n" + new_content[main_pos:]
    f = open("D:/11111/english-tutor-app/server.py", "w", encoding="utf-8")
    f.write(new_content)
    f.close()
    print("Server.py updated successfully")
else:
    print("Function boundaries not found")
    print("old_start:", old_start, "old_end:", old_end)
