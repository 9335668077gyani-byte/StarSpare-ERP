import sys
import math
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QConicalGradient, QBrush, QRadialGradient

class JarvisSplashScreen(QWidget):
    def __init__(self):
        super().__init__()
        # Frameless window with transparent background
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.resize(400, 400)
        
        # Center the window on the screen
        if QApplication.primaryScreen():
            screen_geometry = QApplication.primaryScreen().geometry()
            x = (screen_geometry.width() - self.width()) // 2
            y = (screen_geometry.height() - self.height()) // 2
            self.move(x, y)

        # Animation states
        self.angle_outer = 0
        self.angle_middle = 0
        self.angle_inner = 0
        self.pulse_val = 0
        
        # Timer for 60 FPS animation (16ms)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)

    def update_animation(self):
        # Update angles for rotation - FASTER SPEEDS
        self.angle_outer = (self.angle_outer - 3) % 360  # 3x faster Counter-Clockwise
        self.angle_middle = (self.angle_middle + 6) % 360 # 2x faster Clockwise
        self.angle_inner = (self.angle_inner + 12) % 360  # 1.5x faster Clockwise
        
        # Update pulse value for scaling
        self.pulse_val += 0.15  # Slightly faster pulse
        
        # Trigger repaint
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Setup geometry
        rect = self.rect()
        w = rect.width()
        h = rect.height()
        center_x = w / 2
        center_y = h / 2
        
        # Move origin to center for easier rotation
        painter.translate(center_x, center_y)
        
        # Define Colors
        color_neon_cyan = QColor(0, 255, 255)
        color_electric_blue = QColor(0, 120, 255, 180) # Semi-transparent blue
        color_white = QColor(255, 255, 255)
        
        # --- 1. Outer Ring (Blue, Segmented, Rotates CCW) ---
        painter.save()
        painter.rotate(self.angle_outer)
        
        pen_outer = QPen(color_electric_blue, 6)
        pen_outer.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_outer)
        
        radius_outer = 320
        span = radius_outer / 2
        
        # Draw 3 large segments
        for i in range(0, 360, 120):
            # drawArc(rect, startAngle * 16, spanAngle * 16)
            painter.drawArc(QRectF(-span, -span, radius_outer, radius_outer), i * 16, 90 * 16)
            
        # Draw thin detail ring inside outer
        pen_thin = QPen(QColor(0, 200, 255, 100), 2)
        painter.setPen(pen_thin)
        # Offset angle slightly
        painter.drawArc(QRectF(-(span-10), -(span-10), radius_outer-20, radius_outer-20), 0, 360 * 16)
        
        painter.restore()

        # --- 2. Middle Ring (Cyan, Complex Tech-arcs, Rotates CW) ---
        painter.save()
        painter.rotate(self.angle_middle)
        
        pen_middle = QPen(color_neon_cyan, 4)
        pen_middle.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen_middle)
        
        radius_middle = 240
        span_m = radius_middle / 2
        
        # Draw tech-style arcs (asymmetrical)
        # Arc 1: 0 to 60 deg
        painter.drawArc(QRectF(-span_m, -span_m, radius_middle, radius_middle), 0 * 16, 60 * 16)
        # Arc 2: 90 to 140 deg
        painter.drawArc(QRectF(-span_m, -span_m, radius_middle, radius_middle), 90 * 16, 50 * 16)
        # Arc 3: 180 to 200 deg (small blip)
        painter.drawArc(QRectF(-span_m, -span_m, radius_middle, radius_middle), 180 * 16, 20 * 16)
        # Arc 4: 240 to 330 deg
        painter.drawArc(QRectF(-span_m, -span_m, radius_middle, radius_middle), 240 * 16, 90 * 16)
        
        # Add some dots/decorations on the ends of arcs
        painter.setBrush(QBrush(color_neon_cyan))
        # No easy way to calculate end points without trig, skipping dots for clean look or use rotate/draw
        
        painter.restore()

        # --- 3. Inner Core (White/Cyan, Pulses, Rotates Fast) ---
        painter.save()
        
        # Pulsing effect: Scale between 0.9 and 1.1
        scale_factor = 1.0 + 0.1 * math.sin(self.pulse_val)
        painter.scale(scale_factor, scale_factor)
        
        # Rotation
        painter.rotate(self.angle_inner)
        
        radius_inner = 140
        span_i = radius_inner / 2
        
        # Create a gradient for the core glow
        gradient = QRadialGradient(0, 0, span_i)
        gradient.setColorAt(0.0, QColor(0, 255, 255, 150)) # Center transparency
        gradient.setColorAt(0.8, QColor(0, 255, 255, 50))
        gradient.setColorAt(1.0, Qt.GlobalColor.transparent)
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(QRectF(-span_i, -span_i, radius_inner, radius_inner))
        
        # Draw solid geometric core (triangle/circle shape)
        pen_core = QPen(color_white, 3)
        painter.setPen(pen_core)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # Draw a triangle or hexagon shape for "tech" look
        # Just a triangle for simplicity and rotation visibility
        p1 = (0, -span_i + 20)
        p2 = (-span_i + 20, span_i - 20)
        p3 = (span_i - 20, span_i - 20)
        # Actually let's draw a segmented circle for better spin visibility
        painter.drawArc(QRectF(-(span_i-10), -(span_i-10), radius_inner-20, radius_inner-20), 0, 100 * 16)
        painter.drawArc(QRectF(-(span_i-10), -(span_i-10), radius_inner-20, radius_inner-20), 180 * 16, 100 * 16)
        
        painter.restore()

        # --- 4. Center Text "INITIALIZING..." ---
        painter.save()
        
        # Choose a font
        font = QFont("Segoe UI", 14, QFont.Weight.Bold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        painter.setFont(font)
        
        text = "INITIALIZING..."
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(text)
        text_height = metrics.descent() + metrics.ascent()
        
        # Center position
        x_text = -text_width / 2
        y_text = (metrics.ascent() - metrics.descent()) / 2
        
        # Glow Effect (Shadow)
        painter.setPen(QColor(0, 120, 255, 100))
        painter.drawText(int(x_text + 2), int(y_text + 2), text)
        
        # Main Text
        painter.setPen(color_neon_cyan)
        painter.drawText(int(x_text), int(y_text), text)
        
        painter.restore()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = JarvisSplashScreen()
    window.show()
    sys.exit(app.exec())
