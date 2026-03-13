import os

def update_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace globals
    content = content.replace('STYLE_INPUT_CYBER', 'ui_theme.get_lineedit_style()')
    content = content.replace('STYLE_NEON_BUTTON', 'ui_theme.get_primary_button_style()')
    content = content.replace('STYLE_TABLE_CYBER', 'ui_theme.get_table_style()')

    # Add missing import
    if 'import ui_theme' not in content:
        content = content.replace('from report_generator import ReportGenerator', 'from report_generator import ReportGenerator\nimport ui_theme')

    if 'ProTableDelegate' not in content:
        content = content.replace('from custom_components import ProMessageBox', 'from custom_components import ProMessageBox, ProTableDelegate')

    # Hook delegate
    hook_target = 'self.table.setStyleSheet(ui_theme.get_table_style())\n        page_table_layout.addWidget(self.table)'
    hook_replacement = '''self.table.setStyleSheet(ui_theme.get_table_style())
        
        self.delegate = ProTableDelegate(self.table)
        for c in range(self.table.columnCount()): 
             self.table.setItemDelegateForColumn(c, self.delegate)

        page_table_layout.addWidget(self.table)'''
    content = content.replace(hook_target, hook_replacement)

    # Convert excel button
    btn_xl_target = 'btn_export.setStyleSheet(f"color: {COLOR_ACCENT_GREEN}; border: 1px solid {COLOR_ACCENT_GREEN}; border-radius: 4px; padding: 5px 15px; font-weight: bold;")'
    btn_xl_replace = 'btn_export.setStyleSheet(ui_theme.get_ghost_button_style())'
    content = content.replace(btn_xl_target, btn_xl_replace)

    # Convert pdf button
    btn_pdf_target = 'btn_export_pdf.setStyleSheet(f"color: {COLOR_ACCENT_RED}; border: 1px solid {COLOR_ACCENT_RED}; border-radius: 4px; padding: 5px 15px; font-weight: bold;")'
    btn_pdf_replace = 'btn_export_pdf.setStyleSheet(ui_theme.get_ghost_button_style())'
    content = content.replace(btn_pdf_target, btn_pdf_replace)

    # Inject data to create_item
    item_target = '''            def create_item(text, is_return=False):
                item = QTableWidgetItem(str(text))
                if is_return:'''
    item_replace = '''            def create_item(text, is_return=False):
                item = QTableWidgetItem(str(text))
                item.setData(Qt.ItemDataRole.UserRole, {'type': 'generic'})
                if is_return:'''
    content = content.replace(item_target, item_replace)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

update_file('c:/Users/Admin/Desktop/spare_ERP/reports_page.py')
print('Updated reports_page.py successfully')
