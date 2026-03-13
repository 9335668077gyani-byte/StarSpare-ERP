import os

def update_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace globals
    content = content.replace('STYLE_INPUT_CYBER', 'ui_theme.get_lineedit_style()')
    content = content.replace('STYLE_NEON_BUTTON', 'ui_theme.get_primary_button_style()')

    # Add missing import
    if 'import ui_theme' not in content:
        content = content.replace('from custom_components import ProMessageBox, ProDialog', 'from custom_components import ProMessageBox, ProDialog, ProTableDelegate\nimport ui_theme')
    elif 'ProTableDelegate' not in content:
        content = content.replace('from custom_components import ProMessageBox, ProDialog', 'from custom_components import ProMessageBox, ProDialog, ProTableDelegate')

    # Replace LoginHistoryDialog table styles
    table_style_target = '''        table.setStyleSheet(STYLE_TABLE_CYBER)'''
        
    table_style_replacement = '''        table.setStyleSheet(ui_theme.get_table_style())
        
        delegate = ProTableDelegate(table)
        for c in range(table.columnCount()): 
             table.setItemDelegateForColumn(c, delegate)'''
    content = content.replace(table_style_target, table_style_replacement)

    # Inject UserRole data for table items
    table_item_target = '''        for i, (time, det) in enumerate(history_data):
            table.setItem(i, 0, QTableWidgetItem(str(time)))
            table.setItem(i, 1, QTableWidgetItem(str(det)))'''
                    
    table_item_replacement = '''        for i, (time, det) in enumerate(history_data):
            item1 = QTableWidgetItem(str(time))
            item1.setData(Qt.ItemDataRole.UserRole, {'type': 'generic'})
            table.setItem(i, 0, item1)
            
            item2 = QTableWidgetItem(str(det))
            item2.setData(Qt.ItemDataRole.UserRole, {'type': 'generic'})
            table.setItem(i, 1, item2)'''
    content = content.replace(table_item_target, table_item_replacement)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

update_file('c:/Users/Admin/Desktop/spare_ERP/user_management_page.py')
print('Updated user_management_page.py successfully')
