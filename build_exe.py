import PyInstaller.__main__
import os

# Define the build command
# --noconsole: Hides the terminal window
# --onefile: Bundles everything into a single EXE
# --name: Name of the output file
# --add-data: Include non-code files (styles, empty folders if needed)
# --hidden-import: Ensure all PyQt6 modules are found
# --icon: (Optional) Path to icon file

print("🚀 Starting Build Process for SpareParts Pro v1.5...")

PyInstaller.__main__.run([
    # PyInstaller arguments - Updated to match successful manual build
    'main.py',
    '--name=SpareParts_Pro_v1.5',
    '--noconfirm',
    '--onedir',
    '--windowed',
    '--icon=logo.ico',
    '--add-data=requirements.txt;.',
    '--add-data=logos;logos',
    '--hidden-import=pandas',
    '--hidden-import=matplotlib',
    # Explicit hidden imports for lazy loaded pages
    '--hidden-import=dashboard_page',
    '--hidden-import=billing_page',
    '--hidden-import=inventory_page',
    '--hidden-import=reports_page',
    '--hidden-import=expense_page',
    '--hidden-import=user_management_page',
    '--hidden-import=purchase_order_page',
    '--hidden-import=settings_page',
    '--clean',
    # We don't embed the DB, it's created dynamically in AppData.
    # We might want to embed the logo if it was static, but user uploads it.
])

print("✅ Build Complete! Check the 'dist' folder for SparePartsPro_v1.5.exe")
input("Press Enter to close...")
