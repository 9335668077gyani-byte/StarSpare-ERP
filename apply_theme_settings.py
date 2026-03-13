import os

def update_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace globals
    content = content.replace('STYLE_INPUT_CYBER', 'ui_theme.get_lineedit_style()')

    # Add missing import
    if 'import ui_theme' not in content:
        content = content.replace('from custom_components import ProMessageBox', 'from custom_components import ProMessageBox, ProTableDelegate\nimport ui_theme')
        
    elif 'ProTableDelegate' not in content:
        content = content.replace('from custom_components import ProMessageBox', 'from custom_components import ProMessageBox, ProTableDelegate')

    # Replace table_hsn styles
    hsn_style_target = '''        self.table_hsn.setStyleSheet("""
            QTableWidget { background-color: #111; color: #fff; gridline-color: #333; border: 1px solid #333; border-radius: 6px; }
            QHeaderView::section { background-color: #1a1a1a; color: #00f2ff; padding: 5px; border: 1px solid #333; font-weight: bold; }
        """)'''
        
    hsn_style_replacement = '''        self.table_hsn.setStyleSheet(ui_theme.get_table_style())
        
        self.delegate_hsn = ProTableDelegate(self.table_hsn)
        for c in range(self.table_hsn.columnCount()): 
             self.table_hsn.setItemDelegateForColumn(c, self.delegate_hsn)'''
    content = content.replace(hsn_style_target, hsn_style_replacement)

    # Inject UserRole data for table_hsn items
    table_hsn_item_target = '''            self.table_hsn.setItem(idx, 0, QTableWidgetItem(str(row_data[0])))
            self.table_hsn.setItem(idx, 1, QTableWidgetItem(str(row_data[1])))
            self.table_hsn.setItem(idx, 2, QTableWidgetItem(f"{cgst}%"))
            self.table_hsn.setItem(idx, 3, QTableWidgetItem(f"{sgst}%"))
            self.table_hsn.setItem(idx, 4, QTableWidgetItem(f"{total_gst}%"))
            
            for col in range(5):
                item = self.table_hsn.item(idx, col)
                if item: item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)'''
    
    table_hsn_item_replacement = '''            self.table_hsn.setItem(idx, 0, QTableWidgetItem(str(row_data[0])))
            self.table_hsn.setItem(idx, 1, QTableWidgetItem(str(row_data[1])))
            self.table_hsn.setItem(idx, 2, QTableWidgetItem(f"{cgst}%"))
            self.table_hsn.setItem(idx, 3, QTableWidgetItem(f"{sgst}%"))
            self.table_hsn.setItem(idx, 4, QTableWidgetItem(f"{total_gst}%"))
            
            for col in range(5):
                item = self.table_hsn.item(idx, col)
                if item: 
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setData(Qt.ItemDataRole.UserRole, {'type': 'generic'})'''
    content = content.replace(table_hsn_item_target, table_hsn_item_replacement)

    # Replace results_table styles
    res_style_target = '''        results_table.setStyleSheet("""
            QTableWidget { background-color: #111; color: #fff; gridline-color: #333; border: 1px solid #333; border-radius: 6px; }
            QHeaderView::section { background-color: #1a1a1a; color: #00f2ff; padding: 5px; border: 1px solid #333; font-weight: bold; }
            QTableWidget::item:selected { background-color: #00f2ff; color: black; }
        """)'''
        
    res_style_replacement = '''        results_table.setStyleSheet(ui_theme.get_table_style())
        
        delegate_results = ProTableDelegate(results_table)
        for c in range(results_table.columnCount()): 
             results_table.setItemDelegateForColumn(c, delegate_results)'''
    content = content.replace(res_style_target, res_style_replacement)

    # Inject UserRole data for results_table items
    res_table_item_target = '''                results_table.setItem(idx, 0, QTableWidgetItem(entry["code"]))
                results_table.setItem(idx, 1, QTableWidgetItem(entry["description"]))
                results_table.setItem(idx, 2, QTableWidgetItem(f"{entry['cgst']}"))
                results_table.setItem(idx, 3, QTableWidgetItem(f"{entry['sgst']}"))
                results_table.setItem(idx, 4, QTableWidgetItem(entry.get("category", "")))
                for col in range(5):
                    item = results_table.item(idx, col)
                    if item: item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)'''
                    
    res_table_item_replacement = '''                results_table.setItem(idx, 0, QTableWidgetItem(entry["code"]))
                results_table.setItem(idx, 1, QTableWidgetItem(entry["description"]))
                results_table.setItem(idx, 2, QTableWidgetItem(f"{entry['cgst']}"))
                results_table.setItem(idx, 3, QTableWidgetItem(f"{entry['sgst']}"))
                results_table.setItem(idx, 4, QTableWidgetItem(entry.get("category", "")))
                for col in range(5):
                    item = results_table.item(idx, col)
                    if item: 
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        item.setData(Qt.ItemDataRole.UserRole, {'type': 'generic'})'''
    content = content.replace(res_table_item_target, res_table_item_replacement)


    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

update_file('c:/Users/Admin/Desktop/spare_ERP/settings_page.py')
print('Updated settings_page.py successfully')
