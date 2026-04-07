import PyInstaller.__main__
import os

print("=" * 60)
print("  SpareParts Pro v1.5 — EXE Build Script")
print("=" * 60)

PyInstaller.__main__.run([
    'main.py',
    '--name=SpareParts_Pro_v1.5',
    '--noconfirm',
    '--onefile',
    '--windowed',
    '--icon=logo.ico',

    # ── Bundled read-only assets ──────────────────────────────────
    '--add-data=logo.ico;.',
    '--add-data=assets;assets',
    '--add-data=nexses_ecatalog.db;.',
    '--add-data=logos;logos',
    '--add-data=requirements.txt;.',

    # ── PyQt6 (full collection) ───────────────────────────────────
    '--hidden-import=PyQt6',
    '--hidden-import=PyQt6.QtCore',
    '--hidden-import=PyQt6.QtGui',
    '--hidden-import=PyQt6.QtWidgets',
    '--hidden-import=PyQt6.sip',
    '--hidden-import=PyQt6.QtCharts',
    '--hidden-import=PyQt6.QtPrintSupport',
    '--hidden-import=PyQt6.QtNetwork',
    '--collect-all=PyQt6',

    # ── App pages (lazy-loaded) ───────────────────────────────────
    '--hidden-import=path_utils',
    '--hidden-import=dashboard_page',
    '--hidden-import=billing_page',
    '--hidden-import=billing_animations',
    '--hidden-import=inventory_page',
    '--hidden-import=reports_page',
    '--hidden-import=expense_page',
    '--hidden-import=user_management_page',
    '--hidden-import=purchase_order_page',
    '--hidden-import=settings_page',
    '--hidden-import=catalog_page',

    # ── App modules ───────────────────────────────────────────────
    '--hidden-import=database_manager',
    '--hidden-import=db_config',
    '--hidden-import=db_engine',
    '--hidden-import=data_importer',
    '--hidden-import=invoice_generator',
    '--hidden-import=report_generator',
    '--hidden-import=return_dialog',
    '--hidden-import=custom_components',
    '--hidden-import=styles',
    '--hidden-import=ui_theme',
    '--hidden-import=apply_theme',
    '--hidden-import=apply_theme_expense',
    '--hidden-import=apply_theme_reports',
    '--hidden-import=apply_theme_settings',
    '--hidden-import=apply_theme_user',
    '--hidden-import=apply_theme_vendor',
    '--hidden-import=splash_screen',
    '--hidden-import=login_window',
    '--hidden-import=main_window',
    '--hidden-import=logger',
    '--hidden-import=license_manager',
    '--hidden-import=license_dialog',
    '--hidden-import=hardware_id',
    '--hidden-import=network_setup',
    '--hidden-import=backup_manager',
    '--hidden-import=vendor_manager',
    '--hidden-import=whatsapp_helper',
    '--hidden-import=ai_manager',
    '--hidden-import=auto_enrich_worker',
    '--hidden-import=vehicle_compat_engine',
    '--hidden-import=hsn_sync_engine',
    '--hidden-import=hsn_reference_data',
    '--hidden-import=api_sync_engine',
    '--hidden-import=tvs_catalog_client',
    '--hidden-import=public_key',

    # ── Data / Reporting libs ─────────────────────────────────────
    '--hidden-import=pandas',
    '--hidden-import=pandas.io.formats.excel',
    '--hidden-import=openpyxl',
    '--hidden-import=openpyxl.styles',
    '--hidden-import=openpyxl.utils',
    '--hidden-import=openpyxl.writer.excel',
    '--hidden-import=matplotlib',
    '--hidden-import=matplotlib.backends.backend_agg',
    '--hidden-import=matplotlib.backends.backend_qtagg',   # correct for PyQt6
    '--hidden-import=matplotlib.backends.backend_qt6agg',  # explicit Qt6 alias
    '--hidden-import=reportlab',
    '--hidden-import=reportlab.pdfgen',
    '--hidden-import=reportlab.lib.pagesizes',
    '--hidden-import=reportlab.lib.colors',
    '--hidden-import=reportlab.platypus',
    '--hidden-import=reportlab.lib.styles',
    '--hidden-import=PIL',
    '--hidden-import=PIL.Image',

    # ── Network / stdlib ──────────────────────────────────────────
    '--hidden-import=requests',
    '--hidden-import=cryptography',
    '--hidden-import=cryptography.hazmat.primitives',
    '--hidden-import=cryptography.hazmat.backends',

    '--clean',
    '--workpath=build2',
])

print("\n" + "=" * 60)
print("  Build complete! Check dist/SpareParts_Pro_v1.5.exe")
print("=" * 60)
input("Press Enter to close...")
