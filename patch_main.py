import re
with open('main.py', 'r', encoding='utf-8') as f:
    data = f.read()
data = data.replace('if login.exec():', 'if True:')
data = data.replace('if login_state["authenticated"]:', 'if True:')
with open('main_test.py', 'w', encoding='utf-8') as f:
    f.write(data)
