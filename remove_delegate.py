with open('c:/Users/Admin/Desktop/spare_ERP/inventory_page.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
start = -1
end = -1
for i, line in enumerate(lines):
    if line.startswith('class BladeDelegate'):
        start = i
    if line.startswith('class DataLoadThread'):
        end = i
        break
if start != -1 and end != -1:
    new_lines = lines[:start] + lines[end:]
    for i, line in enumerate(new_lines):
        if 'from custom_components import' in line:
            new_lines[i] = line.replace('ProMessageBox', 'ProMessageBox, ProTableDelegate')
            break
    with open('c:/Users/Admin/Desktop/spare_ERP/inventory_page.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print('BladeDelegate removed and import updated.')
else:
    print('Could not find BladeDelegate or DataLoadThread')
