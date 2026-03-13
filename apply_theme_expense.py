import os

def update_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace globals
    content = content.replace('STYLE_INPUT_CYBER', 'ui_theme.get_lineedit_style()')
    content = content.replace('STYLE_NEON_BUTTON', 'ui_theme.get_primary_button_style()')

    # Add missing import
    if 'import ui_theme' not in content:
        content = content.replace('from logger import app_logger', 'from logger import app_logger\nimport ui_theme')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

update_file('c:/Users/Admin/Desktop/spare_ERP/expense_page.py')
print('Updated expense_page.py successfully')
