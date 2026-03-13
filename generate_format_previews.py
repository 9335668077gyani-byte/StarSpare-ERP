"""
Generate preview thumbnail images for 5 invoice formats.
Each preview is a small PDF-like mockup showing the layout structure.
Uses ReportLab to draw the layout, then converts to PNG via PIL.
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, Color

PREVIEW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "format_previews")
os.makedirs(PREVIEW_DIR, exist_ok=True)

W, H = 200, 283  # A4 ratio thumbnail

def c_rgb(hex_color):
    h = hex_color.lstrip('#')
    return (int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255)

BLUE = c_rgb("#1a4fa0")
ORANGE = c_rgb("#E67E22")
GOLD = c_rgb("#d4a017")
BLACK = (0.1, 0.1, 0.1)
GRAY = (0.6, 0.6, 0.6)
LGRAY = (0.93, 0.93, 0.95)
WHITE = (1, 1, 1)
DARK = (0.2, 0.2, 0.2)


def draw_rect(c, x, y, w, h, fill=None, stroke=None, lw=0.5):
    if fill:
        c.setFillColorRGB(*fill)
    if stroke:
        c.setStrokeColorRGB(*stroke)
        c.setLineWidth(lw)
    c.rect(x, y, w, h, fill=1 if fill else 0, stroke=1 if stroke else 0)


def draw_lines(c, rows, x, y, w, rh, color=GRAY):
    """Draw horizontal lines for table rows."""
    for i in range(rows + 1):
        ry = y - i * rh
        c.setStrokeColorRGB(*color)
        c.setLineWidth(0.3)
        c.line(x, ry, x + w, ry)


def draw_text_block(c, x, y, w, h, color=LGRAY):
    """Draw a small rectangle representing text."""
    draw_rect(c, x, y, w, h, fill=color)


# ─────────────────────── FORMAT 1: MODERN ────────────────────────
def draw_modern(filepath):
    c_obj = canvas.Canvas(filepath, pagesize=(W, H))
    c_obj.setFillColorRGB(1,1,1)
    c_obj.rect(0, 0, W, H, fill=1, stroke=0)
    
    # Header - logo left, shop right
    draw_text_block(c_obj, 10, H-30, 20, 20, BLUE)  # Logo box
    draw_text_block(c_obj, 130, H-18, 60, 6, DARK)   # Shop name
    draw_text_block(c_obj, 145, H-26, 45, 4, GRAY)   # Address
    draw_text_block(c_obj, 155, H-32, 35, 4, GRAY)   # Phone
    
    # INVOICE title
    draw_text_block(c_obj, 10, H-50, 45, 8, BLUE)
    # Invoice meta
    draw_text_block(c_obj, 10, H-62, 35, 4, GRAY)
    draw_text_block(c_obj, 10, H-68, 40, 4, GRAY)
    
    # Divider line
    c_obj.setStrokeColorRGB(*BLUE)
    c_obj.setLineWidth(1)
    c_obj.line(10, H-75, W-10, H-75)
    
    # Bill To / Vehicle
    draw_text_block(c_obj, 10, H-88, 30, 5, DARK)
    draw_text_block(c_obj, 10, H-96, 50, 4, GRAY)
    draw_text_block(c_obj, 120, H-88, 40, 5, DARK)
    draw_text_block(c_obj, 120, H-96, 55, 4, GRAY)
    
    # Table header bar
    draw_rect(c_obj, 10, H-115, W-20, 10, fill=BLUE)
    
    # Table rows with alternating stripes
    rh = 9
    for i in range(8):
        ry = H - 125 - i * rh
        if i % 2 == 0:
            draw_rect(c_obj, 10, ry - rh, W-20, rh, fill=LGRAY)
        draw_text_block(c_obj, 12, ry - 5, 6, 3, GRAY)
        draw_text_block(c_obj, 22, ry - 5, 50, 3, DARK)
        draw_text_block(c_obj, 140, ry - 5, 20, 3, GRAY)
        draw_text_block(c_obj, 165, ry - 5, 22, 3, DARK)
    
    # Total box
    y_tot = H - 125 - 8 * rh - 15
    draw_rect(c_obj, 120, y_tot, 70, 14, fill=BLUE)
    draw_text_block(c_obj, 125, y_tot + 5, 30, 5, WHITE)
    draw_text_block(c_obj, 165, y_tot + 5, 20, 5, WHITE)
    
    # Footer
    c_obj.setStrokeColorRGB(*GRAY)
    c_obj.setLineWidth(0.3)
    c_obj.line(10, 18, W-10, 18)
    draw_text_block(c_obj, 55, 10, 90, 4, GRAY)
    
    c_obj.save()


# ─────────────────────── FORMAT 2: CLASSIC ────────────────────────
def draw_classic(filepath):
    c_obj = canvas.Canvas(filepath, pagesize=(W, H))
    c_obj.setFillColorRGB(1,1,1)
    c_obj.rect(0, 0, W, H, fill=1, stroke=0)
    
    # Outer border
    c_obj.setStrokeColorRGB(*BLACK)
    c_obj.setLineWidth(1.5)
    c_obj.rect(8, 8, W-16, H-16, fill=0, stroke=1)
    
    # Centered header
    draw_text_block(c_obj, 60, H-35, 80, 8, BLACK)  # Shop name centered
    draw_text_block(c_obj, 70, H-45, 60, 4, GRAY)   # Address
    draw_text_block(c_obj, 75, H-51, 50, 4, GRAY)   # Phone/GST
    
    # Double line divider
    c_obj.setLineWidth(1)
    c_obj.line(10, H-58, W-10, H-58)
    c_obj.line(10, H-60, W-10, H-60)
    
    # TAX INVOICE title centered
    draw_text_block(c_obj, 70, H-72, 60, 7, BLACK)
    
    # Invoice details in bordered boxes
    c_obj.setLineWidth(0.5)
    c_obj.rect(10, H-92, 88, 14, fill=0, stroke=1)
    c_obj.rect(102, H-92, 88, 14, fill=0, stroke=1)
    draw_text_block(c_obj, 14, H-84, 40, 4, GRAY)
    draw_text_block(c_obj, 14, H-90, 60, 4, DARK)
    draw_text_block(c_obj, 106, H-84, 35, 4, GRAY)
    draw_text_block(c_obj, 106, H-90, 55, 4, DARK)
    
    # Table with full grid borders
    table_y = H - 105
    cols = [10, 25, 100, 130, 155, W-10]
    rh = 9
    # Header
    draw_rect(c_obj, 10, table_y - rh, W-20, rh, fill=(0.9, 0.9, 0.9))
    # Grid
    for i in range(9):
        ry = table_y - i * rh
        c_obj.setStrokeColorRGB(*BLACK)
        c_obj.setLineWidth(0.3)
        c_obj.line(10, ry, W-10, ry)
    # Vertical lines
    for cx in cols:
        c_obj.line(cx, table_y, cx, table_y - 8 * rh)
    
    # Row content
    for i in range(1, 8):
        ry = table_y - i * rh
        draw_text_block(c_obj, 14, ry - 5, 6, 3, GRAY)
        draw_text_block(c_obj, 28, ry - 5, 55, 3, DARK)
        draw_text_block(c_obj, 103, ry - 5, 18, 3, GRAY)
        draw_text_block(c_obj, 160, ry - 5, 22, 3, DARK)
    
    # Total row bordered
    y_tot = table_y - 8 * rh
    c_obj.setLineWidth(1)
    c_obj.rect(10, y_tot - rh, W-20, rh, fill=0, stroke=1)
    draw_text_block(c_obj, 100, y_tot - 6, 30, 4, BLACK)
    draw_text_block(c_obj, 160, y_tot - 6, 25, 4, BLACK)
    
    # Terms section
    draw_text_block(c_obj, 12, 32, 60, 4, GRAY)
    draw_text_block(c_obj, 12, 26, 80, 3, GRAY)
    draw_text_block(c_obj, 12, 21, 70, 3, GRAY)
    
    c_obj.save()


# ─────────────────────── FORMAT 3: COMPACT ────────────────────────
def draw_compact(filepath):
    c_obj = canvas.Canvas(filepath, pagesize=(W, H))
    c_obj.setFillColorRGB(1,1,1)
    c_obj.rect(0, 0, W, H, fill=1, stroke=0)
    
    # Single thin header row
    draw_rect(c_obj, 5, H-18, W-10, 14, fill=(0.95, 0.95, 0.97))
    draw_text_block(c_obj, 8, H-14, 12, 8, BLUE)   # Small logo
    draw_text_block(c_obj, 24, H-12, 45, 5, DARK)   # Shop name
    draw_text_block(c_obj, 120, H-10, 30, 3, GRAY)  # Invoice#
    draw_text_block(c_obj, 155, H-10, 35, 3, GRAY)  # Date
    draw_text_block(c_obj, 120, H-15, 25, 3, GRAY)
    
    # Customer row (compact)
    draw_text_block(c_obj, 8, H-26, 25, 3, DARK)
    draw_text_block(c_obj, 36, H-26, 50, 3, GRAY)
    draw_text_block(c_obj, 120, H-26, 25, 3, DARK)
    draw_text_block(c_obj, 148, H-26, 45, 3, GRAY)
    
    # Thin divider
    c_obj.setStrokeColorRGB(*GRAY)
    c_obj.setLineWidth(0.3)
    c_obj.line(5, H-30, W-5, H-30)
    
    # Table header (thin)
    draw_rect(c_obj, 5, H-37, W-10, 6, fill=BLUE)
    
    # Dense rows (small rh)
    rh = 6
    for i in range(28):
        ry = H - 43 - i * rh
        if ry < 20: break
        c_obj.setStrokeColorRGB(0.88, 0.88, 0.88)
        c_obj.setLineWidth(0.2)
        c_obj.line(5, ry, W-5, ry)
        draw_text_block(c_obj, 7, ry - 4, 4, 2, GRAY)
        draw_text_block(c_obj, 14, ry - 4, 45, 2, DARK)
        draw_text_block(c_obj, 130, ry - 4, 15, 2, GRAY)
        draw_text_block(c_obj, 165, ry - 4, 22, 2, DARK)
    
    # Inline total at bottom
    draw_rect(c_obj, 120, 8, 72, 10, fill=BLUE)
    draw_text_block(c_obj, 123, 11, 25, 4, WHITE)
    draw_text_block(c_obj, 165, 11, 22, 4, WHITE)
    
    c_obj.save()


# ─────────────────────── FORMAT 4: DETAILED ────────────────────────
def draw_detailed(filepath):
    c_obj = canvas.Canvas(filepath, pagesize=(W, H))
    c_obj.setFillColorRGB(1,1,1)
    c_obj.rect(0, 0, W, H, fill=1, stroke=0)
    
    # Full header with all details
    draw_text_block(c_obj, 10, H-18, 20, 16, ORANGE)  # Logo
    draw_text_block(c_obj, 35, H-14, 60, 6, DARK)     # Shop name
    draw_text_block(c_obj, 35, H-22, 50, 3, GRAY)     # Address
    draw_text_block(c_obj, 35, H-27, 40, 3, GRAY)     # Phone
    draw_text_block(c_obj, 35, H-32, 55, 3, GRAY)     # GSTIN
    
    # Invoice details right
    draw_text_block(c_obj, 130, H-14, 55, 5, DARK)    # TAX INVOICE
    draw_text_block(c_obj, 140, H-22, 45, 3, GRAY)
    draw_text_block(c_obj, 140, H-27, 45, 3, GRAY)
    
    c_obj.setStrokeColorRGB(*ORANGE)
    c_obj.setLineWidth(1)
    c_obj.line(10, H-38, W-10, H-38)
    
    # Bill To + Ship To
    draw_text_block(c_obj, 10, H-47, 25, 4, DARK)
    draw_text_block(c_obj, 10, H-53, 45, 3, GRAY)
    draw_text_block(c_obj, 10, H-58, 40, 3, GRAY)
    draw_text_block(c_obj, 110, H-47, 28, 4, DARK)
    draw_text_block(c_obj, 110, H-53, 50, 3, GRAY)
    draw_text_block(c_obj, 110, H-58, 45, 3, GRAY)
    
    # Wide table with many columns (CGST/SGST split)
    table_y = H - 70
    draw_rect(c_obj, 5, table_y - 8, W-10, 8, fill=ORANGE)
    # Column headers in white
    col_labels_x = [8, 20, 55, 85, 100, 115, 130, 148, 170]
    for cx in col_labels_x:
        draw_text_block(c_obj, cx, table_y - 5, 12, 3, WHITE)
    
    # Rows
    rh = 8
    for i in range(7):
        ry = table_y - 8 - i * rh
        if i % 2 == 0:
            draw_rect(c_obj, 5, ry - rh, W-10, rh, fill=(1.0, 0.98, 0.95))
        draw_text_block(c_obj, 8, ry - 5, 5, 2, GRAY)
        draw_text_block(c_obj, 20, ry - 5, 30, 2, DARK)
        draw_text_block(c_obj, 55, ry - 5, 12, 2, GRAY)
        draw_text_block(c_obj, 85, ry - 5, 10, 2, GRAY)
        draw_text_block(c_obj, 100, ry - 5, 10, 2, GRAY)
        draw_text_block(c_obj, 115, ry - 5, 12, 2, GRAY)
        draw_text_block(c_obj, 130, ry - 5, 14, 2, GRAY)
        draw_text_block(c_obj, 148, ry - 5, 14, 2, GRAY)
        draw_text_block(c_obj, 170, ry - 5, 18, 2, DARK)
    
    # HSN Summary box (bottom left)
    y_bot = table_y - 8 - 7 * rh - 10
    draw_text_block(c_obj, 10, y_bot, 35, 4, DARK)
    draw_rect(c_obj, 10, y_bot - 25, 85, 22, stroke=ORANGE, lw=0.5)
    draw_text_block(c_obj, 12, y_bot - 8, 20, 3, GRAY)
    draw_text_block(c_obj, 40, y_bot - 8, 20, 3, GRAY)
    draw_text_block(c_obj, 65, y_bot - 8, 20, 3, GRAY)
    draw_text_block(c_obj, 12, y_bot - 14, 20, 3, GRAY)
    draw_text_block(c_obj, 40, y_bot - 14, 20, 3, GRAY)
    draw_text_block(c_obj, 65, y_bot - 14, 20, 3, GRAY)
    
    # Amount in words
    draw_text_block(c_obj, 10, y_bot - 32, 40, 3, GRAY)
    draw_text_block(c_obj, 10, y_bot - 37, 90, 3, DARK)
    
    # Total card (right)
    draw_rect(c_obj, 110, y_bot - 8, 80, 12, fill=ORANGE)
    draw_text_block(c_obj, 115, y_bot - 1, 30, 5, WHITE)
    draw_text_block(c_obj, 160, y_bot - 1, 25, 5, WHITE)
    
    c_obj.save()


# ─────────────────────── FORMAT 5: ELEGANT ────────────────────────
def draw_elegant(filepath):
    c_obj = canvas.Canvas(filepath, pagesize=(W, H))
    c_obj.setFillColorRGB(1,1,1)
    c_obj.rect(0, 0, W, H, fill=1, stroke=0)
    
    # Thin accent border
    c_obj.setStrokeColorRGB(*GOLD)
    c_obj.setLineWidth(0.8)
    c_obj.rect(6, 6, W-12, H-12, fill=0, stroke=1)
    
    # Elegant header with generous spacing
    draw_text_block(c_obj, 15, H-25, 18, 16, GOLD)  # Logo
    draw_text_block(c_obj, 40, H-18, 70, 7, DARK)    # Shop name large
    
    # Decorative line under name
    c_obj.setStrokeColorRGB(*GOLD)
    c_obj.setLineWidth(0.8)
    c_obj.line(40, H-25, 110, H-25)
    c_obj.setLineWidth(0.3)
    c_obj.line(40, H-27, 110, H-27)
    
    draw_text_block(c_obj, 40, H-33, 45, 3, GRAY)
    
    # TAX INVOICE right
    draw_text_block(c_obj, 130, H-20, 55, 6, GOLD)
    draw_text_block(c_obj, 140, H-28, 42, 3, GRAY)
    draw_text_block(c_obj, 140, H-33, 42, 3, GRAY)
    
    # Spacious customer section
    y_cust = H - 50
    draw_text_block(c_obj, 15, y_cust, 30, 4, DARK)
    draw_text_block(c_obj, 15, y_cust - 7, 55, 3, GRAY)
    draw_text_block(c_obj, 15, y_cust - 12, 45, 3, GRAY)
    draw_text_block(c_obj, 120, y_cust, 35, 4, DARK)
    draw_text_block(c_obj, 120, y_cust - 7, 60, 3, GRAY)
    
    # Subtle table with rounded-feel header
    table_y = H - 80
    # Rounded header simulation
    draw_rect(c_obj, 12, table_y - 9, W-24, 9, fill=GOLD)
    
    # Soft grid + alternating tint
    rh = 9
    for i in range(7):
        ry = table_y - 9 - i * rh
        if i % 2 == 0:
            draw_rect(c_obj, 12, ry - rh, W-24, rh, fill=(0.99, 0.98, 0.94))
        c_obj.setStrokeColorRGB(0.9, 0.88, 0.82)
        c_obj.setLineWidth(0.2)
        c_obj.line(12, ry, W-12, ry)
        draw_text_block(c_obj, 15, ry - 5, 5, 3, GRAY)
        draw_text_block(c_obj, 24, ry - 5, 50, 3, DARK)
        draw_text_block(c_obj, 145, ry - 5, 18, 3, GRAY)
        draw_text_block(c_obj, 168, ry - 5, 16, 3, DARK)
    
    # Elegant total area
    y_tot = table_y - 9 - 7 * rh - 8
    c_obj.setStrokeColorRGB(*GOLD)
    c_obj.setLineWidth(0.5)
    c_obj.line(110, y_tot + 5, W-12, y_tot + 5)
    draw_text_block(c_obj, 115, y_tot - 3, 25, 4, GRAY)
    draw_text_block(c_obj, 160, y_tot - 3, 22, 4, DARK)
    
    # Grand total
    draw_rect(c_obj, 110, y_tot - 20, 78, 13, fill=GOLD)
    draw_text_block(c_obj, 115, y_tot - 12, 28, 5, WHITE)
    draw_text_block(c_obj, 158, y_tot - 12, 22, 5, WHITE)
    
    # Signature block
    y_sig = y_tot - 40
    draw_text_block(c_obj, 120, y_sig + 5, 55, 3, GRAY)
    c_obj.setStrokeColorRGB(*DARK)
    c_obj.setLineWidth(0.5)
    c_obj.line(130, y_sig, 185, y_sig)
    draw_text_block(c_obj, 135, y_sig - 6, 40, 3, DARK)
    
    # Amount in words (left)
    draw_text_block(c_obj, 15, y_sig + 5, 40, 3, GRAY)
    draw_text_block(c_obj, 15, y_sig - 1, 80, 3, DARK)
    
    # Footer
    c_obj.setStrokeColorRGB(*GOLD)
    c_obj.setLineWidth(0.3)
    c_obj.line(15, 20, W-15, 20)
    draw_text_block(c_obj, 55, 12, 90, 3, GRAY)
    
    c_obj.save()


# ─────────────────────── CONVERT PDF → PNG ────────────────────────
def pdf_to_png(pdf_path, png_path, scale=2):
    """Convert a single-page PDF to PNG using fitz (PyMuPDF) or PIL."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        page = doc[0]
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat)
        pix.save(png_path)
        doc.close()
        os.remove(pdf_path)
        return True
    except ImportError:
        pass
    
    # Fallback: keep PDF, copy as-is reference
    try:
        from PIL import Image
        # Try pdf2image if available
        from pdf2image import convert_from_path
        images = convert_from_path(pdf_path, dpi=150, first_page=1, last_page=1)
        if images:
            images[0].save(png_path, 'PNG')
            os.remove(pdf_path)
            return True
    except ImportError:
        pass
    
    # If no converter available, keep the PDF
    print(f"Warning: Could not convert {pdf_path} to PNG. Keeping PDF.")
    return False


if __name__ == "__main__":
    formats = {
        "Modern": draw_modern,
        "Classic": draw_classic,
        "Compact": draw_compact,
        "Detailed": draw_detailed,
        "Elegant": draw_elegant,
    }
    
    for name, draw_func in formats.items():
        pdf_path = os.path.join(PREVIEW_DIR, f"{name}.pdf")
        png_path = os.path.join(PREVIEW_DIR, f"{name}.png")
        draw_func(pdf_path)
        converted = pdf_to_png(pdf_path, png_path)
        if converted:
            print(f"✓ Generated: {png_path}")
        else:
            print(f"✓ Generated PDF: {pdf_path}")
    
    print(f"\nAll previews saved to: {PREVIEW_DIR}")
