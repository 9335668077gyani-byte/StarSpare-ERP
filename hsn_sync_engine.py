# hsn_sync_engine.py
# One-Touch GST & HSN Sync Engine for Spare ERP
# Scans all inventory parts missing HSN or GST, auto-matches from local DB + reference,
# shows a themed preview table, and saves all confirmed matches in one batch update.

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QFrame, QCheckBox, QWidget, QApplication, QAbstractItemView, QSplitter
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QBrush
import webbrowser
import ui_theme
from styles import (
    COLOR_ACCENT_CYAN, COLOR_ACCENT_GREEN, COLOR_ACCENT_RED,
    COLOR_ACCENT_AMBER, COLOR_TEXT_PRIMARY, COLOR_SURFACE
)
from hsn_reference_data import HSN_REFERENCE_DB, auto_assign_hsn


# ─────────────────────────────────────────────────────────────────────────────
# Background scan thread — keeps the UI responsive during heavy DB reads
# ─────────────────────────────────────────────────────────────────────────────
class HsnScanThread(QThread):
    """Scans all parts and runs smart local HSN matching in background."""
    progress   = pyqtSignal(int)        # 0-100
    result_ready = pyqtSignal(list)     # List of match dicts
    status_msg = pyqtSignal(str)
    aborted    = pyqtSignal()           # Fired when user aborts

    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self._abort = False             # Abort flag

    def abort(self):
        """Signal the thread to stop cleanly on next iteration."""
        self._abort = True

    def run(self):
        self.status_msg.emit("🔍 Pre-loading HSN rules...")
        # ── Pre-load ALL rules into memory once → zero per-part DB calls ──
        try:
            all_rules_raw = self.db_manager.get_hsn_rules()  # list of (id, pattern, hsn_code, desc, gst_rate, rule_type)
            # Build a dict: pattern_lower → (hsn_code, gst_rate)
            self._rule_cache = {str(r[1]).lower(): (str(r[2]), float(r[4]))
                                for r in all_rules_raw if r[1] and r[2]}
        except Exception:
            self._rule_cache = {}

        self.status_msg.emit("🔍 Scanning inventory...")
        parts = self.db_manager.get_all_parts()
        total = len(parts)
        results = []

        for i, part in enumerate(parts):
            # ── Check abort flag every iteration ──
            if self._abort:
                self.status_msg.emit(f"⛔ Scan aborted after {i} parts.")
                self.aborted.emit()
                return

            part_id   = str(part[0])
            part_name = str(part[1])
            category  = str(part[10]) if len(part) > 10 else ""
            curr_hsn  = str(part[15]).strip() if len(part) > 15 else ""
            curr_gst  = part[16] if len(part) > 16 else None

            # ── Enhanced needs_sync: also catch date strings and absurd GST rates ──
            hsn_bad = (not curr_hsn or curr_hsn in ("", "None", "N/A")
                       or any(c in curr_hsn for c in ['-', ':'])  # date pattern
                       or not curr_hsn.replace('.', '').isdigit())
            gst_bad  = (curr_gst is None or str(curr_gst) in ("", "None", "0", "0.0")
                        or (curr_gst is not None and float(curr_gst or 0) > 100))
            needs_sync = hsn_bad or gst_bad

            suggested_hsn, suggested_gst, confidence, source = self._smart_match(
                part_name, category, curr_hsn, curr_gst
            )

            results.append({
                'part_id':       part_id,
                'part_name':     part_name,
                'category':      category,
                'current_hsn':   curr_hsn,
                'current_gst':   curr_gst,
                'suggested_hsn': suggested_hsn,
                'suggested_gst': suggested_gst,
                'confidence':    confidence,
                'source':        source,
                'needs_sync':    needs_sync,
                'selected':      needs_sync,
            })

            self.progress.emit(int((i + 1) / total * 100))

        self.status_msg.emit(f"✅ Scan complete — {sum(1 for r in results if r['needs_sync'])} parts need sync")
        self.result_ready.emit(results)

    def _smart_match(self, name, category, curr_hsn, curr_gst):
        """Returns (hsn, gst, confidence_pct, source_label). Uses in-memory cache — zero DB calls."""
        # 1. Already has valid data → keep it, full confidence
        hsn_ok = (curr_hsn and curr_hsn not in ("", "None", "N/A")
                  and not any(c in curr_hsn for c in ['-', ':'])
                  and curr_hsn.replace('.', '').isdigit())
        if hsn_ok and curr_gst:
            try:
                g = float(curr_gst)
                if 0 < g <= 100:
                    return curr_hsn, g, 100, "✅ Existing"
            except Exception:
                pass

        # 2. In-memory rule cache (replaces per-part DB call)
        name_lower = name.lower()
        cat_lower  = category.lower()

        if name_lower in self._rule_cache:
            h, g = self._rule_cache[name_lower]
            return h, g, 90, "🧠 Learned"
        if cat_lower and cat_lower in self._rule_cache:
            h, g = self._rule_cache[cat_lower]
            return h, g, 90, "🧠 Learned"
        # Partial pattern match from cache
        for pattern, (h, g) in self._rule_cache.items():
            if pattern in name_lower or name_lower in pattern:
                return h, g, 85, "🧠 Learned"

        # 3. Local Reference DB — keyword match on name words
        cat_lower_ref = category.lower()
        kw = [w for w in name_lower.split() if len(w) > 3]
        for ref in HSN_REFERENCE_DB:
            desc = ref['description'].lower()
            if name_lower in desc or cat_lower_ref in desc or any(w in desc for w in kw):
                gst = ref['cgst'] + ref['sgst']
                return ref['code'], gst, 75, f"📚 Reference ({ref['category']})"

        # 4. auto_assign_hsn fallback
        hsn, gst = auto_assign_hsn(name)
        return hsn, gst, 50, "🔮 Auto-Assign"

# ─────────────────────────────────────────────────────────────────────────────
# Background Apply Thread — batch-updates DB in a single transaction
# ─────────────────────────────────────────────────────────────────────────────
class HsnApplyThread(QThread):
    """Applies HSN/GST updates to the database in one batched transaction."""
    progress    = pyqtSignal(int)       # 0-100
    status_msg  = pyqtSignal(str)
    done        = pyqtSignal(int)       # success_count
    aborted     = pyqtSignal(int)       # success_count so far

    def __init__(self, db_manager, to_sync):
        super().__init__()
        self.db_manager = db_manager
        self.to_sync    = to_sync
        self._abort     = False

    def abort(self):
        self._abort = True

    def run(self):
        total         = len(self.to_sync)
        success_count = 0
        learn_batch   = []   # (pattern, hsn, gst) to batch-learn

        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            for i, r in enumerate(self.to_sync):
                if self._abort:
                    conn.commit()
                    self.status_msg.emit(f"⛔ Aborted — {success_count} saved.")
                    self.aborted.emit(success_count)
                    return

                try:
                    hsn  = str(r['suggested_hsn']).split('.')[0]  # strip trailing .0
                    gst  = float(r['suggested_gst'])
                    cursor.execute(
                        "UPDATE parts SET hsn_code=?, gst_rate=? WHERE part_id=?",
                        (hsn, gst, r['part_id'])
                    )
                    success_count += 1
                    learn_batch.append((r['part_name'], hsn, gst))
                except Exception as e:
                    from logger import app_logger
                    app_logger.warning(f"HSN apply failed for {r['part_id']}: {e}")

                self.progress.emit(int((i + 1) / total * 100))

            conn.commit()

            # Batch-learn all rules in one transaction
            for pattern, hsn, gst in learn_batch:
                if pattern and hsn:
                    try:
                        conn.execute("""
                            INSERT INTO hsn_master (pattern, hsn_code, description, gst_rate, rule_type)
                            VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT(pattern) DO UPDATE SET
                            hsn_code=excluded.hsn_code, gst_rate=excluded.gst_rate, rule_type='learned'
                        """, (pattern, hsn, pattern, gst, 'learned'))
                    except Exception:
                        pass
            conn.commit()

        except Exception as e:
            conn.rollback()
            self.status_msg.emit(f"❌ Error: {e}")
        finally:
            conn.close()

        self.status_msg.emit(f"✅ Synced {success_count}/{total} parts successfully!")
        self.done.emit(success_count)


# ─────────────────────────────────────────────────────────────────────────────
# Main HSN Sync Dialog
# ─────────────────────────────────────────────────────────────────────────────
class HsnSyncDialog(QDialog):
    """
    One-Touch GST & HSN Sync Engine — with live abort support.
    """
    sync_completed = pyqtSignal(int)

    def __init__(self, parent, db_manager):
        super().__init__(parent)
        self.db_manager = db_manager
        self.scan_results = []
        self._apply_aborted = False     # Abort flag for apply loop
        self.setWindowTitle("🔄 HSN & GST Sync Engine")
        self.setMinimumSize(1100, 680)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #0b0b14;
                color: {COLOR_TEXT_PRIMARY};
                font-family: 'Segoe UI';
            }}
            QLabel {{ background: transparent; border: none; }}
            QHeaderView::section {{
                background: #141428;
                color: {COLOR_ACCENT_CYAN};
                border: 1px solid #223;
                font-weight: bold;
                font-size: 11px;
                padding: 5px;
            }}
        """)
        self._build_ui()

    # ── UI Construction ────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        # ── Header ──
        hdr = QFrame()
        hdr.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 rgba(0,229,255,0.12), stop:1 rgba(0,255,65,0.06));
                border: 1px solid rgba(0,229,255,0.3);
                border-radius: 10px;
            }
        """)
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(20, 12, 20, 12)

        title = QLabel("⚡ ONE-TOUCH HSN & GST SYNC ENGINE")
        title.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-weight: bold; font-size: 15px; letter-spacing: 1px;")
        hdr_layout.addWidget(title)
        hdr_layout.addStretch()

        self.lbl_status = QLabel("Press SCAN to begin...")
        self.lbl_status.setStyleSheet("color: #aaa; font-size: 12px;")
        hdr_layout.addWidget(self.lbl_status)
        root.addWidget(hdr)

        # ── Configuration Row ──
        c_row = QHBoxLayout()
        c_row.setContentsMargins(0, 0, 0, 10)
        
        c_row.addStretch()
        root.addLayout(c_row)

        # ── Progress Bar ──
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ background: #1a1a2e; border: none; border-radius: 3px; }}
            QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {COLOR_ACCENT_CYAN}, stop:1 {COLOR_ACCENT_GREEN}); border-radius: 3px; }}
        """)
        root.addWidget(self.progress_bar)

        # ── Stats Row ──
        stat_row = QHBoxLayout()
        self.stat_total   = self._stat_chip("TOTAL PARTS", "—", COLOR_ACCENT_CYAN)
        self.stat_missing = self._stat_chip("MISSING HSN/GST", "—", COLOR_ACCENT_RED)
        self.stat_matched = self._stat_chip("MATCHED", "—", COLOR_ACCENT_GREEN)
        self.stat_selected= self._stat_chip("SELECTED", "—", COLOR_ACCENT_AMBER)
        for w in [self.stat_total, self.stat_missing, self.stat_matched, self.stat_selected]:
            stat_row.addWidget(w)
        root.addLayout(stat_row)

        # ── Table ──
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "✓", "PART ID", "PART NAME", "CURRENT HSN", "CURRENT GST%",
            "SUGGESTED HSN", "SUGGESTED GST%", "CONFIDENCE", "SOURCE"
        ])
        self.table.setStyleSheet(ui_theme.get_table_style())
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        hdr_view = self.table.horizontalHeader()
        hdr_view.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table)

        # ── Filter Buttons Row ──
        filter_row = QHBoxLayout()

        self.btn_select_missing = QPushButton("☑️ Select Missing Only")
        self.btn_select_missing.setStyleSheet(self._ghost_btn(COLOR_ACCENT_RED))
        self.btn_select_missing.setFixedHeight(32)
        self.btn_select_missing.clicked.connect(self._select_missing_only)
        filter_row.addWidget(self.btn_select_missing)

        self.btn_select_all = QPushButton("☑️ Select All")
        self.btn_select_all.setStyleSheet(self._ghost_btn(COLOR_ACCENT_CYAN))
        self.btn_select_all.setFixedHeight(32)
        self.btn_select_all.clicked.connect(self._select_all)
        filter_row.addWidget(self.btn_select_all)

        self.btn_deselect  = QPushButton("☐ Deselect All")
        self.btn_deselect.setStyleSheet(self._ghost_btn("#888"))
        self.btn_deselect.setFixedHeight(32)
        self.btn_deselect.clicked.connect(self._deselect_all)
        filter_row.addWidget(self.btn_deselect)

        filter_row.addStretch()

        self.btn_verify_gst = QPushButton("🌐 Verify on GST Portal")
        self.btn_verify_gst.setStyleSheet(self._ghost_btn(COLOR_ACCENT_AMBER))
        self.btn_verify_gst.setFixedHeight(32)
        self.btn_verify_gst.setToolTip("Opens the official GST HSN/SAC search and copies selected HSN to clipboard")
        self.btn_verify_gst.clicked.connect(self._verify_on_gst_portal)
        filter_row.addWidget(self.btn_verify_gst)

        root.addLayout(filter_row)

        # ── Action Buttons Row ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_scan = QPushButton("🔍  SCAN INVENTORY")
        self.btn_scan.setFixedHeight(44)
        self.btn_scan.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_scan.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0,229,255,0.1);
                color: {COLOR_ACCENT_CYAN};
                border: 2px solid {COLOR_ACCENT_CYAN};
                border-radius: 8px; font-weight: bold; font-size: 13px;
            }}
            QPushButton:hover {{ background: {COLOR_ACCENT_CYAN}; color: black; }}
        """)
        self.btn_scan.clicked.connect(self._start_scan)
        btn_row.addWidget(self.btn_scan)

        # ABORT button — hidden by default, shown during scan & apply
        self.btn_abort = QPushButton("⛔  ABORT")
        self.btn_abort.setFixedHeight(44)
        self.btn_abort.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_abort.setVisible(False)
        self.btn_abort.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,60,60,0.15);
                color: {COLOR_ACCENT_RED};
                border: 2px solid {COLOR_ACCENT_RED};
                border-radius: 8px; font-weight: bold; font-size: 13px;
            }}
            QPushButton:hover {{ background: {COLOR_ACCENT_RED}; color: white; }}
        """)
        self.btn_abort.clicked.connect(self._do_abort)
        btn_row.addWidget(self.btn_abort)

        btn_row.addStretch()

        self.btn_cancel = QPushButton("CLOSE")
        self.btn_cancel.setFixedHeight(44)
        self.btn_cancel.setFixedWidth(100)
        self.btn_cancel.setStyleSheet(ui_theme.get_icon_btn_red())
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_apply = QPushButton("⚡  APPLY SYNC TO DATABASE")
        self.btn_apply.setFixedHeight(44)
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.setEnabled(False)
        self.btn_apply.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0,255,65,0.1);
                color: {COLOR_ACCENT_GREEN};
                border: 2px solid {COLOR_ACCENT_GREEN};
                border-radius: 8px; font-weight: bold; font-size: 13px;
                padding: 0 20px;
            }}
            QPushButton:hover {{ background: {COLOR_ACCENT_GREEN}; color: black; }}
            QPushButton:disabled {{ opacity: 0.4; }}
        """)
        self.btn_apply.clicked.connect(self._apply_sync)
        btn_row.addWidget(self.btn_apply)

        root.addLayout(btn_row)

    # ── Stat Chip Helper ───────────────────────────────────────────────────
    def _stat_chip(self, label, value, color):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: rgba({QColor(color).red()},{QColor(color).green()},{QColor(color).blue()},0.08);
                border: 1px solid {color};
                border-radius: 8px;
            }}
        """)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(2)
        lbl_val = QLabel(value)
        lbl_val.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: bold; font-family: Consolas;")
        lbl_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_lbl = QLabel(label)
        lbl_lbl.setStyleSheet("color: #888; font-size: 10px; letter-spacing: 1px;")
        lbl_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl_val)
        lay.addWidget(lbl_lbl)
        # Store reference to value label for updates
        frame._value_label = lbl_val
        return frame

    def _update_stat(self, chip, val):
        chip._value_label.setText(str(val))

    def _ghost_btn(self, color):
        return f"""
            QPushButton {{
                background: rgba({QColor(color).red()},{QColor(color).green()},{QColor(color).blue()},0.08);
                color: {color}; border: 1px solid {color};
                border-radius: 5px; font-size: 11px; padding: 0 10px;
            }}
            QPushButton:hover {{ background: {color}; color: black; }}
        """

    # ── Scan Logic ─────────────────────────────────────────────────────────
    def _start_scan(self):
        self.btn_scan.setVisible(False)
        self.btn_abort.setVisible(True)
        self.btn_abort.setText("⛔  ABORT SCAN")
        self.btn_apply.setEnabled(False)
        self.table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("🔍 Scanning inventory...")

        self._scan_thread = HsnScanThread(self.db_manager)
        self._scan_thread.progress.connect(self.progress_bar.setValue)
        self._scan_thread.status_msg.connect(self.lbl_status.setText)
        self._scan_thread.result_ready.connect(self._on_scan_done)
        self._scan_thread.aborted.connect(self._on_scan_aborted)
        self._scan_thread.start()

    def _on_scan_aborted(self):
        """Called when thread aborted before completing."""
        self.btn_abort.setVisible(False)
        self.btn_scan.setVisible(True)
        self.btn_scan.setEnabled(True)
        self.progress_bar.setValue(0)

    def _on_scan_done(self, results):
        self.scan_results = results
        self._populate_table(results)
        # Restore normal button state
        self.btn_abort.setVisible(False)
        self.btn_scan.setVisible(True)
        self.btn_scan.setEnabled(True)
        self.btn_apply.setEnabled(True)

        total    = len(results)
        missing  = sum(1 for r in results if r['needs_sync'])
        matched  = sum(1 for r in results if r['suggested_hsn'] and r['suggested_hsn'] != '87089900'
                       and r['confidence'] >= 75)
        selected = sum(1 for r in results if r['selected'])

        self._update_stat(self.stat_total,   total)
        self._update_stat(self.stat_missing, missing)
        self._update_stat(self.stat_matched, matched)
        self._update_stat(self.stat_selected, selected)

    # ── Table Population ───────────────────────────────────────────────────
    def _populate_table(self, results):
        self.table.setRowCount(0)
        self.table.setRowCount(len(results))

        for row_i, r in enumerate(results):
            # Col 0 — Checkbox
            chk = QCheckBox()
            chk.setChecked(r['selected'])
            chk.setStyleSheet(ui_theme.get_checkbox_style())
            chk.stateChanged.connect(lambda state, idx=row_i: self._on_check_changed(idx, state))
            cw = QWidget()
            cl = QHBoxLayout(cw); cl.setContentsMargins(0,0,0,0); cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(chk)
            self.table.setCellWidget(row_i, 0, cw)

            # Col 1 — Part ID
            self._set_item(row_i, 1, r['part_id'], COLOR_ACCENT_CYAN, bold=True)

            # Col 2 — Part Name
            self._set_item(row_i, 2, r['part_name'])

            # Col 3 — Current HSN
            curr_hsn = r['current_hsn'] or "—"
            clr = COLOR_ACCENT_RED if r['needs_sync'] else COLOR_ACCENT_GREEN
            self._set_item(row_i, 3, curr_hsn, clr)

            # Col 4 — Current GST%
            curr_gst = str(r['current_gst']) if r['current_gst'] else "—"
            self._set_item(row_i, 4, curr_gst, clr)

            # Col 5 — Suggested HSN
            self._set_item(row_i, 5, r['suggested_hsn'], COLOR_ACCENT_GREEN, bold=True)

            # Col 6 — Suggested GST%
            self._set_item(row_i, 6, f"{r['suggested_gst']:.1f}%", COLOR_ACCENT_GREEN, bold=True)

            # Col 7 — Confidence badge
            conf = r['confidence']
            conf_color = (COLOR_ACCENT_GREEN if conf >= 80
                          else COLOR_ACCENT_AMBER if conf >= 60
                          else COLOR_ACCENT_RED)
            self._set_item(row_i, 7, f"{conf}%", conf_color, bold=True)

            # Col 8 — Source
            self._set_item(row_i, 8, r['source'])

            # Row background — highlight rows needing sync
            if r['needs_sync']:
                for col in range(9):
                    itm = self.table.item(row_i, col)
                    if itm:
                        itm.setBackground(QBrush(QColor(255, 80, 80, 18)))

    def _set_item(self, row, col, text, color=None, bold=False):
        itm = QTableWidgetItem(str(text))
        itm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if color:
            itm.setForeground(QBrush(QColor(color)))
        if bold:
            f = QFont(); f.setBold(True); itm.setFont(f)
        self.table.setItem(row, col, itm)

    # ── Selection Helpers ──────────────────────────────────────────────────
    def _on_check_changed(self, idx, state):
        if idx < len(self.scan_results):
            self.scan_results[idx]['selected'] = bool(state)
        sel = sum(1 for r in self.scan_results if r['selected'])
        self._update_stat(self.stat_selected, sel)

    def _select_all(self):
        self._set_all_checks(True)

    def _deselect_all(self):
        self._set_all_checks(False)

    def _select_missing_only(self):
        for row_i, r in enumerate(self.scan_results):
            checked = r['needs_sync']
            r['selected'] = checked
            cw = self.table.cellWidget(row_i, 0)
            if cw:
                chk = cw.findChild(QCheckBox)
                if chk:
                    chk.blockSignals(True)
                    chk.setChecked(checked)
                    chk.blockSignals(False)
        sel = sum(1 for r in self.scan_results if r['selected'])
        self._update_stat(self.stat_selected, sel)

    def _set_all_checks(self, state: bool):
        for row_i, r in enumerate(self.scan_results):
            r['selected'] = state
            cw = self.table.cellWidget(row_i, 0)
            if cw:
                chk = cw.findChild(QCheckBox)
                if chk:
                    chk.blockSignals(True)
                    chk.setChecked(state)
                    chk.blockSignals(False)
        self._update_stat(self.stat_selected, len(self.scan_results) if state else 0)

    # ── GST Portal Verify ─────────────────────────────────────────────────
    def _verify_on_gst_portal(self):
        """Copy HSN of selected row to clipboard, open GST portal."""
        selected_rows = self.table.selectedItems()
        hsn = None
        if selected_rows:
            row = self.table.currentRow()
            hsn_item = self.table.item(row, 5)
            if hsn_item:
                hsn = hsn_item.text()
        if hsn:
            QApplication.clipboard().setText(hsn)
        webbrowser.open("https://services.gst.gov.in/services/searchhsnsac")

    # ── Apply Sync ─────────────────────────────────────────────────────────
    def _apply_sync(self):
        to_sync = [r for r in self.scan_results if r['selected']]
        if not to_sync:
            return

        self._apply_aborted = False
        self.btn_apply.setEnabled(False)
        self.btn_apply.setText("⏳  Syncing...")
        self.btn_cancel.setVisible(False)
        self.btn_abort.setVisible(True)
        self.btn_abort.setText("⛔  ABORT APPLY")
        self.progress_bar.setValue(0)
        QApplication.processEvents()

        # ── Run in background thread — single batch transaction ──
        self._apply_thread = HsnApplyThread(self.db_manager, to_sync)
        self._apply_thread.progress.connect(self.progress_bar.setValue)
        self._apply_thread.status_msg.connect(self.lbl_status.setText)
        self._apply_thread.done.connect(self._on_apply_done)
        self._apply_thread.aborted.connect(self._on_apply_aborted)
        self._apply_thread.start()

    def _on_apply_done(self, success_count):
        self.btn_abort.setVisible(False)
        self.btn_cancel.setVisible(True)
        self.btn_apply.setText("⚡  APPLY SYNC TO DATABASE")
        self.btn_apply.setEnabled(True)
        self.progress_bar.setValue(100)
        self.sync_completed.emit(success_count)
        QTimer.singleShot(300, self._start_scan)

    def _on_apply_aborted(self, success_count):
        self.btn_abort.setVisible(False)
        self.btn_cancel.setVisible(True)
        self.btn_apply.setText("⚡  APPLY SYNC TO DATABASE")
        self.btn_apply.setEnabled(True)
        if success_count > 0:
            self.sync_completed.emit(success_count)

    # ── Abort Handlers ─────────────────────────────────────────────────────
    def _do_abort(self):
        """Called when user presses ABORT — handles both scan and apply."""
        # Abort scan thread if running
        if hasattr(self, '_scan_thread') and self._scan_thread.isRunning():
            self._scan_thread.abort()
        # Abort apply thread if running
        if hasattr(self, '_apply_thread') and self._apply_thread.isRunning():
            self._apply_thread.abort()
        self.btn_abort.setEnabled(False)
        self.btn_abort.setText("⛔  Stopping...")
        self.lbl_status.setText("⛔ Aborting... please wait.")
