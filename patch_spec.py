import re
with open('SpareParts_Pro_v1.5.spec', 'r', encoding='utf-8') as f:
    data = f.read()
if 'PyQt6.QtSvg' not in data:
    data = data.replace("'PyQt6.QtCharts',", "'PyQt6.QtCharts', 'PyQt6.QtSvg',")
    with open('SpareParts_Pro_v1.5.spec', 'w', encoding='utf-8') as f:
        f.write(data)
