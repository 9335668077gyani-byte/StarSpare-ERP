import os

target_dir = r'c:\MY PROJECTS\spare_ERP'
replacements = [
    ('ui_theme.get_primary_button_style()', 'ui_theme.get_primary_button_style()'),
    ('ui_theme.get_primary_button_style()', 'ui_theme.get_primary_button_style()'),
    ('ui_theme.get_success_button_style()', 'ui_theme.get_success_button_style()'),
    ('ui_theme.get_danger_button_style()', 'ui_theme.get_danger_button_style()'),
]

for root, _, files in os.walk(target_dir):
    for strin in files:
        if strin.endswith('.py') and strin != 'styles.py' and strin != 'ui_theme.py' and not strin.startswith('apply_'):
            fp = os.path.join(root, strin)
            with open(fp, 'r', encoding='utf-8') as f:
                content = f.read()
            
            orig = content
            for old, new in replacements:
                content = content.replace(old, new)
            
            if content != orig:
                with open(fp, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f'Updated {strin}')
print('Done!')
