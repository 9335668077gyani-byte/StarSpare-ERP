import re
with open('catalog_page.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('ap_cols = ["SEL", "Part Code", "Description"', 'ap_cols = ["SEL", "PART CODE", "Description"')
with open('catalog_page.py', 'w', encoding='utf-8') as f:
    f.write(text)
