with open('SpareParts_Pro_v1.5.spec', 'r', encoding='utf-8') as f:
    spec = f.read()
spec = spec.replace("'main.py'", "'main_test.py'")
with open('test.spec', 'w', encoding='utf-8') as f:
    f.write(spec)
