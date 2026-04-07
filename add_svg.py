import re
with open('main.py', 'r', encoding='utf-8') as f:
    data = f.read()
if 'PyQt6.QtSvg' not in data:
    data = data.replace('import sys', 'import sys\nimport PyQt6.QtSvg')
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(data)
