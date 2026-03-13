import os

def update_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Add missing import
    if 'import ui_theme' not in content:
        content = content.replace('from custom_components import ProMessageBox', 'from custom_components import ProMessageBox, ProTableDelegate\nimport ui_theme')
    elif 'ProTableDelegate' not in content:
        content = content.replace('from custom_components import ProMessageBox', 'from custom_components import ProMessageBox, ProTableDelegate')

    # Replace inline style fallbacks with ui_theme
    content = content.replace('STYLE_NEON_BUTTON if STYLE_NEON_BUTTON else "background-color: #00E5FF; color: black; padding: 5px;"', 'ui_theme.get_primary_button_style()')
    content = content.replace('STYLE_INPUT_CYBER if STYLE_INPUT_CYBER else "background: #333; color: white;"', 'ui_theme.get_lineedit_style()')
    content = content.replace('STYLE_NEON_BUTTON if STYLE_NEON_BUTTON else "background: green; color: white;"', 'ui_theme.get_primary_button_style()')
    content = content.replace('STYLE_DANGER_BUTTON if STYLE_DANGER_BUTTON else "background: red; color: white;"', 'ui_theme.get_danger_button_style()')

    # Replace table style
    table_style_target = 'self.table_vendors.setStyleSheet(STYLE_TABLE_CYBER if STYLE_TABLE_CYBER else "background: #222; color: white;")'
    table_style_replacement = '''self.table_vendors.setStyleSheet(ui_theme.get_table_style())
        
        self.delegate_vendors = ProTableDelegate(self.table_vendors)
        for c in range(self.table_vendors.columnCount()): 
             self.table_vendors.setItemDelegateForColumn(c, self.delegate_vendors)'''
    content = content.replace(table_style_target, table_style_replacement)

    # Inject UserRole data
    item_target = '''                self.table_vendors.setItem(row, 0, QTableWidgetItem(str(v[0])))
                self.table_vendors.setItem(row, 1, QTableWidgetItem(str(v[1])))
                self.table_vendors.setItem(row, 2, QTableWidgetItem(str(v[3])))
                self.table_vendors.setItem(row, 3, QTableWidgetItem(str(v[5])))'''
                
    item_replacement = '''                for col_idx, text in enumerate([str(v[0]), str(v[1]), str(v[3]), str(v[5])]):
                    item = QTableWidgetItem(text)
                    item.setData(Qt.ItemDataRole.UserRole, {'type': 'generic'})
                    self.table_vendors.setItem(row, col_idx, item)'''
    content = content.replace(item_target, item_replacement)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

update_file('c:/Users/Admin/Desktop/spare_ERP/vendor_manager.py')
print('Updated vendor_manager.py successfully')
