from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QWidget, QFrame, QCompleter, QApplication)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from styles import (COLOR_BACKGROUND, COLOR_SURFACE, COLOR_ACCENT_CYAN, 
                    STYLE_NEON_BUTTON, STYLE_INPUT_CYBER, STYLE_TABLE_CYBER, STYLE_DANGER_BUTTON)

class CustomerLedgerDialog(QDialog):
    def __init__(self, db_manager, prefill_customer=""):
        super().__init__()
        self.db_manager = db_manager
        self.prefill_customer = prefill_customer
        self.setWindowTitle("Customer Ledger & Statement")
        self.setFixedSize(900, 600)
        self.setStyleSheet(f"background-color: {COLOR_BACKGROUND};")
        self._setup_ui()
        self._load_customers()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Search Header
        search_layout = QHBoxLayout()
        lbl_search = QLabel("Select Customer:")
        lbl_search.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-size: 14px; font-weight: bold;")
        self.txt_customer = QLineEdit()
        self.txt_customer.setStyleSheet(STYLE_INPUT_CYBER)
        self.txt_customer.setPlaceholderText("Start typing customer name...")
        if self.prefill_customer:
            self.txt_customer.setText(self.prefill_customer)
            
        btn_view = QPushButton("View Ledger")
        btn_view.setStyleSheet(STYLE_NEON_BUTTON)
        btn_view.clicked.connect(self._load_ledger)
        
        search_layout.addWidget(lbl_search)
        search_layout.addWidget(self.txt_customer)
        search_layout.addWidget(btn_view)
        layout.addLayout(search_layout)
        
        # Summary Header
        self.summary_frame = QFrame()
        self.summary_frame.setStyleSheet(f"background-color: {COLOR_SURFACE}; border-radius: 8px;")
        sum_layout = QHBoxLayout(self.summary_frame)
        
        def _make_stat(title, val="Rs. 0.00", color="#ffffff"):
            lbl_title = QLabel(title)
            lbl_title.setStyleSheet("color: #888888; font-size: 11px;")
            lbl_val = QLabel(val)
            lbl_val.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
            vbox = QVBoxLayout()
            vbox.addWidget(lbl_title)
            vbox.addWidget(lbl_val)
            w = QWidget()
            w.setLayout(vbox)
            return w, lbl_val
            
        w1, self.lbl_total_billed = _make_stat("TOTAL BILLED", color=COLOR_ACCENT_CYAN)
        w2, self.lbl_total_paid = _make_stat("TOTAL PAID", color="#25d366")
        w3, self.lbl_total_due = _make_stat("TOTAL OUTSTANDING", color="#ff4444")
        
        sum_layout.addWidget(w1)
        sum_layout.addWidget(w2)
        sum_layout.addWidget(w3)
        layout.addWidget(self.summary_frame)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Date", "Invoice ID", "Total", "Paid", "Due", "Status", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 140)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.verticalHeader().setMinimumSectionSize(38)
        self.table.setStyleSheet(STYLE_TABLE_CYBER)
        layout.addWidget(self.table)
        
        # Export Button
        self.btn_export = QPushButton("📄 Export Statement to PDF")
        self.btn_export.setStyleSheet(STYLE_NEON_BUTTON)
        self.btn_export.clicked.connect(self._export_pdf)
        layout.addWidget(self.btn_export, alignment=Qt.AlignmentFlag.AlignRight)
        
    def _load_customers(self):
        names = self.db_manager.get_all_customer_names()
        completer = QCompleter(names, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.txt_customer.setCompleter(completer)
        if self.prefill_customer:
            self._load_ledger()
            
    def _load_ledger(self):
        name = self.txt_customer.text().strip()
        if not name:
            return
            
        rows = self.db_manager.get_customer_ledger(name)
        self.table.setRowCount(len(rows))
        
        tot_billed = 0
        tot_paid = 0
        tot_due = 0
        self.ledger_data = [] # for PDF export
        
        for i, r in enumerate(rows):
            inv_id = str(r[0])
            date = str(r[1])
            total = float(r[2] or 0)
            paid = float(r[3] or 0)
            due = float(r[4] or 0)
            
            tot_billed += total
            tot_paid += paid
            tot_due += due
            
            status = "PAID" if due <= 0.01 else "DUE"
            
            self.table.setItem(i, 0, QTableWidgetItem(date.split()[0]))
            self.table.setItem(i, 1, QTableWidgetItem(inv_id))
            self.table.setItem(i, 2, QTableWidgetItem(f"Rs. {total:,.2f}"))
            self.table.setItem(i, 3, QTableWidgetItem(f"Rs. {paid:,.2f}"))
            
            due_item = QTableWidgetItem(f"Rs. {due:,.2f}")
            if due > 0.01:
                due_item.setForeground(QColor("#ff4444"))
            self.table.setItem(i, 4, due_item)
            
            stat_item = QTableWidgetItem(status)
            if status == "PAID":
                stat_item.setForeground(QColor("#25d366"))
            else:
                stat_item.setForeground(QColor("#ff4444"))
            self.table.setItem(i, 5, stat_item)
            
            if due > 0.01:
                btn = QPushButton("Collect Due")
                btn.setStyleSheet(STYLE_DANGER_BUTTON + " QPushButton { padding: 4px 10px; font-size: 11px; letter-spacing: 0px; min-height: 22px; }")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda ch, inv=inv_id, dr=i: self._collect_due(inv, dr))
                
                cw = QWidget()
                cw.setStyleSheet("background: transparent;")
                cl = QHBoxLayout(cw)
                cl.setContentsMargins(6, 4, 6, 4)
                cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cl.addWidget(btn)
                
                self.table.setCellWidget(i, 6, cw)
                
            self.ledger_data.append([date, inv_id, total, paid, due, status])
            
        self.lbl_total_billed.setText(f"Rs. {tot_billed:,.2f}")
        self.lbl_total_paid.setText(f"Rs. {tot_paid:,.2f}")
        self.lbl_total_due.setText(f"Rs. {tot_due:,.2f}")
        self.current_summary = {"billed": tot_billed, "paid": tot_paid, "due": tot_due}
        
    def _collect_due(self, invoice_id, row_index):
        """Collect due payment inline — mirrors reports_page.collect_due_payment logic."""
        from billing_page import PaymentDialog
        from custom_components import ProMessageBox

        # Fetch current payment state from DB
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT payment_due, payment_cash, payment_upi, total_amount FROM invoices WHERE invoice_id=?",
                (invoice_id,)
            )
            row = cur.fetchone()
        finally:
            conn.close()

        if not row:
            ProMessageBox.warning(self, "Not Found", f"Invoice {invoice_id} not found.")
            return

        existing_due, existing_cash, existing_upi, total_amount = (
            float(row[0] or 0), float(row[1] or 0), float(row[2] or 0), float(row[3] or 0)
        )

        dlg = PaymentDialog(existing_due, invoice_id, self)
        if dlg.exec() != 1:
            return

        new_cash, new_upi, new_due, mode = dlg.get_result()

        final_cash = existing_cash + new_cash
        final_upi  = existing_upi  + new_upi
        final_due  = max(0.0, existing_due - new_cash - new_upi)

        if final_cash > 0 and final_upi > 0:
            final_mode = "SPLIT"
        elif final_upi > 0:
            final_mode = "UPI"
        else:
            final_mode = "CASH"
        if final_due > 0:
            final_mode = "PARTIAL" if (final_cash + final_upi) > 0 else "DUE"

        ok, msg = self.db_manager.update_invoice_payment(
            invoice_id, final_cash, final_upi, final_due, final_mode
        )
        if ok:
            if new_cash > 0:
                self.db_manager.log_payment(invoice_id, new_cash, 'CASH')
            if new_upi > 0:
                self.db_manager.log_payment(invoice_id, new_upi, 'UPI')

            try:
                from invoice_generator import InvoiceGenerator
                ig = InvoiceGenerator(self.db_manager)
                ig.regenerate_invoice(invoice_id, current_qr_amount=new_upi, current_cash_amount=new_cash)
            except Exception:
                pass  # PDF regeneration is best-effort from this dialog

            if final_due <= 0:
                ProMessageBox.information(self, "Paid", f"Invoice #{invoice_id} is now fully paid!")
            else:
                ProMessageBox.information(self, "Partial", f"Collected. Remaining due: Rs. {final_due:,.2f}")

            self._load_ledger()  # Refresh the ledger table
        else:
            ProMessageBox.critical(self, "Error", f"Could not update payment: {msg}")

        
    def _export_pdf(self):
        name = self.txt_customer.text().strip()
        if not name or not hasattr(self, 'ledger_data') or not self.ledger_data:
            return
        from report_generator import generate_customer_statement_pdf
        generate_customer_statement_pdf(name, self.ledger_data, self.current_summary)
