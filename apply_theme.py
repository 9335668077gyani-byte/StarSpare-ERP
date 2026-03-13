import os

def update_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace inputs
    content = content.replace('STYLE_INPUT_CYBER', 'ui_theme.get_lineedit_style()')
    # Replace neon buttons
    content = content.replace('STYLE_NEON_BUTTON', 'ui_theme.get_primary_button_style()')
    # Replace tables
    content = content.replace('STYLE_TABLE_CYBER', 'ui_theme.get_table_style()')

    # Add missing import if needed
    if 'import ui_theme' not in content:
        content = content.replace('from logger import app_logger', 'from logger import app_logger\nimport ui_theme')

    # Check ProTableDelegate import
    if 'ProTableDelegate' not in content:
        content = content.replace('from custom_components import ProMessageBox, ProDialog', 'from custom_components import ProMessageBox, ProDialog, ProTableDelegate')

    # Hook delegate
    hook_target = 'self.cart_table.setShowGrid(True) # Explicit Grid\n        right_layout.addWidget(self.cart_table)'
    hook_replacement = '''self.cart_table.setShowGrid(True) # Explicit Grid
        
        self.delegate = ProTableDelegate(self.cart_table)
        for c in range(self.cart_table.columnCount()): 
             self.cart_table.setItemDelegateForColumn(c, self.delegate)
             
        right_layout.addWidget(self.cart_table)'''
    content = content.replace(hook_target, hook_replacement)

    # Update item creation to inject dict so ProDialog works
    item_target = '''            def create_item(val, align=Qt.AlignmentFlag.AlignCenter):
                it = QTableWidgetItem(str(val))
                it.setTextAlignment(align)
                return it'''

    item_replacement = '''            def create_item(val, align=Qt.AlignmentFlag.AlignCenter):
                it = QTableWidgetItem(str(val))
                it.setTextAlignment(align)
                it.setData(Qt.ItemDataRole.UserRole, {'type': 'generic'})
                return it'''
    content = content.replace(item_target, item_replacement)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

update_file('c:/Users/Admin/Desktop/spare_ERP/billing_page.py')
print('Updated billing_page.py successfully')
