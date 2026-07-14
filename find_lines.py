import re
with open(r'D:\22222\英语网站\english-tutor-app\server.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines, 1):
    if '# Stage' in line and '# Stage' in line.split('#')[0]:
        pass
    if 'threading.Lock()' in line:
        print(f'Line {i}: {line.rstrip()}')
    if 'stage = int(data' in line or 'line.replace("# ", "")' in line:
        print(f'Line {i}: {repr(line.rstrip())}')
    if 'if line.startswith' in line and 'Stage' in line:
        print(f'Line {i}: {repr(line.rstrip())}')
