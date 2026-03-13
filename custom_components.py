from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QWidget, QGraphicsDropShadowEffect, QGraphicsOpacityEffect)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF, QPoint, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import (QColor, QFont, QPainter, QPainterPath, QPen, QBrush, 
                          QRadialGradient, QLinearGradient)
import math
import time
from styles import COLOR_ACCENT_CYAN, STYLE_NEON_BUTTON, COLOR_ACCENT_AMBER, COLOR_ACCENT_GREEN, COLOR_ACCENT_RED
import random

class TechCard(QFrame):
    """
    A custom frame with 'Clipped Corners' and Neon Glow.
    Simulates the 'Mechanical' HUD look.
    """
    def __init__(self, title, value_widget, glow_color=COLOR_ACCENT_CYAN, parent=None):
        super().__init__(parent)
        self.glow_color = QColor(glow_color)
        self.title = title
        self.value_widget = value_widget
        self.setMinimumHeight(100) # Increased for sparkline
        
        # Setup Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(25, 15, 25, 15)
        self.layout.setSpacing(5)
        
        # Title
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet(f"color: #8899aa; font-size: 11px; font-weight: 700; letter-spacing: 1px; font-family: 'Segoe UI'; border: none; background: transparent;")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.lbl_title)
        
        # Value (Passed Widget)
        self.value_widget.setStyleSheet(f"color: white; font-size: 24px; font-weight: bold; border: none; background: transparent; font-family: 'Orbitron', 'Segoe UI';")
        self.value_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.value_widget)
        
        # Sparkline
        self.sparkline = SparklineWidget(self.glow_color)
        self.layout.addWidget(self.sparkline)
        
        # Tech Card Levitation Animation
        self.levitation_offset = 0
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.update_levitation)
        self.anim_timer.start(50)

        # Drop Shadow for Neon Glow
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(25)
        self.shadow.setColor(self.glow_color)
        self.shadow.setOffset(0, 0)
        self.setGraphicsEffect(self.shadow)

    def update_levitation(self):
        # Subtle floating motion
        t = time.time() * 2
        self.levitation_offset = math.sin(t) * 5
        
        # Update Shadow Intensity for a more "levitating" feel
        blur = 20 + math.sin(t) * 10
        self.shadow.setBlurRadius(blur)
        
        # Move the entire widget slightly if parent layout allows, 
        # but in a grid/vbox it's better to translate in paintEvent
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Apply Levitation Translation
        painter.translate(0, self.levitation_offset)
        
        rect = QRectF(self.rect())
        rect.adjust(5, 5, -5, -5) # Adjust for floating padding
        
        clip_size = 15.0
        
        path = QPainterPath()
        # Start Top-Left (shifted)
        path.moveTo(rect.left() + clip_size, rect.top())
        # Top-Right
        path.lineTo(rect.right(), rect.top())
        # Bottom-Right (shifted)
        path.lineTo(rect.right(), rect.bottom() - clip_size)
        # Bottom-Right Corner Cut
        path.lineTo(rect.right() - clip_size, rect.bottom())
        # Bottom-Left
        path.lineTo(rect.left(), rect.bottom())
        # Top-Left Corner Cut
        path.lineTo(rect.left(), rect.top() + clip_size)
        path.closeSubpath()
        
        # Draw Background (Glassmorphism Deep Void)
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0, QColor(10, 20, 40, 180))
        grad.setColorAt(1, QColor(5, 10, 20, 120))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)
        
        # Draw Glass Reflection
        reflect_path = QPainterPath()
        reflect_path.moveTo(rect.left() + clip_size, rect.top())
        reflect_path.lineTo(rect.right(), rect.top())
        reflect_path.lineTo(rect.right(), rect.top() + 30)
        reflect_path.lineTo(rect.left(), rect.top() + 30)
        reflect_path.closeSubpath()
        painter.fillPath(reflect_path, QColor(255, 255, 255, 15))
        
        # Draw Border (Neon Plasma)
        pen = QPen(self.glow_color)
        pen.setWidthF(1.2)
        painter.setPen(pen)
        painter.drawPath(path)
        
        # Draw Tech Accents (Little deco lines)
        # Top Left Pattern
        painter.setPen(QPen(self.glow_color, 3))
        painter.drawLine(int(rect.left()), int(rect.top() + clip_size), int(rect.left() + clip_size), int(rect.top()))

        # Bottom Right Pattern
        painter.drawLine(int(rect.right()), int(rect.bottom() - clip_size), int(rect.right() - clip_size), int(rect.bottom()))


class ProDialog(QDialog):
    """Base class for all custom dialogs in the app"""
    def __init__(self, parent=None, title="Dialog", width=400, height=200):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Main Frame with Border
        self.frame = QFrame()
        self.frame.setStyleSheet(f"""
            QFrame {{
                background-color: #0b0b14; 
                border: 1px solid {COLOR_ACCENT_CYAN}; 
                border-radius: 8px;
            }}
        """)
        self.frame_layout = QVBoxLayout(self.frame)
        self.frame_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        self.lbl_title = QLabel(title.upper())
        self.lbl_title.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-weight: bold; font-size: 14px; border: none; margin-bottom: 10px;")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_layout.addWidget(self.lbl_title)
        
        self.layout.addWidget(self.frame)

    def showEvent(self, event):
        super().showEvent(event)
        self.raise_()
        self.activateWindow()
        
        parent = self.parent()
        if parent:
            try:
                # Calculate Parent Center in Global Screen Coordinates
                if isinstance(parent, QWidget):
                    # Get the window (top-level) of the parent to be sure
                    target = parent.window()
                    
                    # Top-left of target in screen coords
                    parent_pos = target.mapToGlobal(QPoint(0, 0))
                    parent_width = target.width()
                    parent_height = target.height()
                    
                    center_x = parent_pos.x() + (parent_width // 2)
                    center_y = parent_pos.y() + (parent_height // 2)
                    
                    # My Dimensions
                    my_w = self.width()
                    my_h = self.height()
                    
                    # Top-Left for Me
                    new_x = center_x - (my_w // 2)
                    new_y = center_y - (my_h // 2)
                    
                    self.move(new_x, new_y)
            except Exception:
                pass # Fallback to default

    def set_content(self, widget):
        """Add content widget to the dialog"""
        self.frame_layout.addWidget(widget)

    def add_buttons(self, buttons_layout):
        """Add button layout to the bottom"""
        self.frame_layout.addLayout(buttons_layout)


class ProMessageBox(ProDialog):
    """Custom replacement for QMessageBox"""
    def __init__(self, parent, title, message, mode="INFO", yes_no=False):
        # Adjust height based on content approx
        super().__init__(parent, title, width=350, height=180)
        
        # Message Label
        self.lbl_msg = QLabel(message)
        self.lbl_msg.setStyleSheet("color: white; font-size: 13px; border: none;")
        self.lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_msg.setWordWrap(True)
        self.frame_layout.addWidget(self.lbl_msg)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        
        # Center the buttons
        btn_layout.addStretch()
        
        if yes_no:
            self.result_val = False
            
            btn_yes = QPushButton("YES")
            btn_yes.setCursor(Qt.CursorShape.PointingHandCursor)
            # Red for delete/critical, Cyan otherwise? Let's stick to standard Neon for Yes or specific colors
            if mode == "DELETE":
                 btn_yes.setStyleSheet("background-color: #f44336; color: white; border: none; border-radius: 4px; padding: 8px; font-weight: bold;")
            else:
                 btn_yes.setStyleSheet(STYLE_NEON_BUTTON)
            
            btn_yes.clicked.connect(self.accept_yes)
            
            btn_no = QPushButton("NO")
            btn_no.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_no.setStyleSheet("background-color: #333; color: white; border: 1px solid #555; border-radius: 4px; padding: 8px;")
            btn_no.clicked.connect(self.reject)
            
            btn_layout.addWidget(btn_yes)
            btn_layout.addWidget(btn_no)
            
        else: # OK Only
            btn_ok = QPushButton("OK")
            btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_ok.setStyleSheet(STYLE_NEON_BUTTON)
            btn_ok.clicked.connect(self.accept)
            btn_layout.addWidget(btn_ok)
            
        btn_layout.addStretch()
        self.frame_layout.addLayout(btn_layout)
        
    def accept_yes(self):
        self.result_val = True
        self.accept()

    @staticmethod
    def information(parent, title, message):
        dlg = ProMessageBox(parent, title, message, mode="INFO")
        dlg.exec()

    @staticmethod
    def warning(parent, title, message):
        dlg = ProMessageBox(parent, title, message, mode="WARNING")
        dlg.exec()

    @staticmethod
    def critical(parent, title, message):
        dlg = ProMessageBox(parent, title, message, mode="CRITICAL")
        dlg.exec()
        
    @staticmethod
    def question(parent, title, message):
        """Returns True for Yes, False for No"""
        dlg = ProMessageBox(parent, title, message, mode="QUESTION", yes_no=True)
        return dlg.exec() == QDialog.DialogCode.Accepted

class CyberSidebarButton(QWidget):
    """
    A futuristic sidebar button with a 'Reactor Box' icon container.
    Structure:
      - Reactor Box (QFrame)
        - Icon Label
      - Text Label (Bottom)
    """
    clicked = pyqtSignal()
    
    def __init__(self, text, icon_text, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(90, 85)
        
        self.is_active = False
        self.is_hovered = False
        self.shimmer_pos = -1.0 # For holographic sweep
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 1. Reactor Box (Container for Icon)
        self.reactor_box = QFrame()
        self.reactor_box.setFixedSize(48, 48)
        
        # Icon inside Box
        self.lbl_icon = QLabel(icon_text, self.reactor_box)
        self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_icon.setGeometry(0, 0, 48, 48)

        # Effect for Pulse
        self.reactor_eff = QGraphicsOpacityEffect(self.reactor_box)
        self.reactor_eff.setOpacity(1.0)
        self.reactor_box.setGraphicsEffect(self.reactor_eff)
        
        layout.addWidget(self.reactor_box)
        
        # 2. Label (Bottom)
        self.lbl_text = QLabel(text)
        self.lbl_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_text.setStyleSheet("font-family: 'Rajdhani', 'Segoe UI';")
        layout.addWidget(self.lbl_text)
        
        # Shimmer Timer
        self.shimmer_timer = QTimer(self)
        self.shimmer_timer.timeout.connect(self._update_shimmer)
        self.shimmer_timer.start(50)

        self.update_style()

    def _update_shimmer(self):
        if self.is_active or self.is_hovered:
            self.shimmer_pos += 0.05
            if self.shimmer_pos > 1.5:
                self.shimmer_pos = -0.5
            self.update()

    def setChecked(self, checked):
        self.is_active = checked
        self.update_style()
        
    def enterEvent(self, event):
        self.is_hovered = True
        self.update_style()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self.is_hovered = False
        self.update_style()
        super().leaveEvent(event)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def click(self):
        """Simulate a click"""
        self.clicked.emit()
        
    def showEvent(self, event):
        super().showEvent(event)
        # Start Pulse Animation
        self.pulse_anim = QPropertyAnimation(self.reactor_eff, b"opacity")
        self.pulse_anim.setDuration(1500)
        self.pulse_anim.setStartValue(0.7)
        self.pulse_anim.setEndValue(1.0)
        self.pulse_anim.setLoopCount(-1) # Infinite
        self.pulse_anim.setEasingCurve(QEasingCurve.Type.CosineCurve)
        self.pulse_anim.start()
            
    def update_style(self):
        lbl_style_base = "background: transparent; border: none; font-family: 'Segoe UI';"
        
        # Cyber Shape: Asymmetric Corners
        shape_style = "border-top-left-radius: 12px; border-bottom-right-radius: 12px; border-top-right-radius: 2px; border-bottom-left-radius: 2px;"
        
        if self.is_active:
            # Active State: HIDDEN REACTOR GLOW (Intense)
            self.reactor_box.setStyleSheet(f"""
                QFrame {{
                    background-color: qradialgradient(cx:0.5, cy:0.5, radius: 1.0, fx:0.5, fy:0.5, stop:0 rgba(0, 242, 255, 0.4), stop:1 transparent);
                    border: 2px solid {COLOR_ACCENT_CYAN};
                    {shape_style}
                    border-left: 3px solid {COLOR_ACCENT_CYAN}; /* Solid Cyan Bar (Spec Update) */
                }}
            """)
            self.lbl_icon.setStyleSheet(f"color: #fff; font-size: 24px; {lbl_style_base}")
            self.lbl_text.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-size: 10px; font-weight: 800; letter-spacing: 2px; font-family: 'Orbitron'; {lbl_style_base}")
            
            # Shimmer is handled in paintEvent
            
        elif self.is_hovered:
             self.reactor_box.setStyleSheet(f"""
                QFrame {{
                    background-color: rgba(0, 242, 255, 0.1);
                    border: 1px solid {COLOR_ACCENT_CYAN};
                    {shape_style}
                }}
            """)
             self.lbl_icon.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-size: 24px; {lbl_style_base}")
             self.lbl_text.setStyleSheet(f"color: white; font-size: 10px; font-weight: bold; letter-spacing: 1.5px; {lbl_style_base}")
            
        else:
            # Inactive State: Dim, Faint Tech
            self.reactor_box.setStyleSheet(f"""
                QFrame {{
                    background-color: rgba(10, 20, 30, 0.6);
                    border: 1px solid rgba(0, 242, 255, 0.15);
                    {shape_style}
                }}
            """)
            self.lbl_icon.setStyleSheet(f"color: #445566; font-size: 24px; {lbl_style_base}")
            self.lbl_text.setStyleSheet(f"color: #445566; font-size: 10px; font-weight: bold; letter-spacing: 1px; {lbl_style_base}")

    def paintEvent(self, event):
        if not (self.is_active or self.is_hovered):
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw Shimmer Sweep across the Reactor Box
        rect = QRectF(self.reactor_box.geometry())
        
        shimmer_grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        c_glow = QColor(COLOR_ACCENT_CYAN)
        c_glow.setAlpha(0)
        c_shimmer = QColor(255, 255, 255, 120)
        
        pos = self.shimmer_pos
        p1 = max(0.0, min(1.0, pos - 0.2))
        p2 = max(0.0, min(1.0, pos))
        p3 = max(0.0, min(1.0, pos + 0.2))
        
        shimmer_grad.setColorAt(p1, c_glow)
        shimmer_grad.setColorAt(p2, c_shimmer)
        shimmer_grad.setColorAt(p3, c_glow)
        
        painter.setBrush(shimmer_grad)
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Use same clip as reactor box
        clip_size = 12.0
        path = QPainterPath()
        path.moveTo(rect.left() + clip_size, rect.top())
        path.lineTo(rect.right(), rect.top())
        path.lineTo(rect.right(), rect.bottom() - clip_size)
        path.lineTo(rect.right() - clip_size, rect.bottom())
        path.lineTo(rect.left(), rect.bottom())
        path.lineTo(rect.left(), rect.top() + clip_size)
        path.closeSubpath()
        
        painter.setOpacity(0.4)
        painter.drawPath(path)

from PyQt6.QtWidgets import QSplashScreen, QApplication
from PyQt6.QtCore import QTimer, Qt, QRectF, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QLinearGradient, QRadialGradient
from styles import COLOR_ACCENT_CYAN

class SciFiSplashScreen(QSplashScreen):
    """
    Sifi Countdown Splash Screen.
    Cellphone Battery Filling Animation.
    """
    finished = pyqtSignal()
    
    def __init__(self):
        # Create a transparent pixmap
        pixmap = QPixmap(500, 300)
        pixmap.fill(Qt.GlobalColor.transparent)
        super().__init__(pixmap)
        
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Center
        if QApplication.primaryScreen():
            screen_geometry = QApplication.primaryScreen().geometry()
            x = (screen_geometry.width() - self.width()) // 2
            y = (screen_geometry.height() - self.height()) // 2
            self.move(x, y)

        # Animation states
        self.start_time = time.time()
        self.duration = 4.0 # Time to charge
        self.charge_val = 0.0 # 0 to 100
        
        self.loading_text = "CHARGING SYSTEM..."
        self.is_finished = False
        
        # Pulse for charging effect
        self.pulse_alpha = 0
        
        # Timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16) # 60 FPS

    def update_animation(self):
        if self.is_finished: return

        elapsed = time.time() - self.start_time
        progress = min(1.0, elapsed / self.duration)
        
        self.charge_val = progress * 100.0
        
        # Pulse logic
        self.pulse_alpha = (math.sin(elapsed * 10) + 1) / 2 # 0 to 1 oscillating
        
        if progress >= 1.0:
            self.is_finished = True
            self.charge_val = 100.0
            self.loading_text = "FULLY CHARGED"
            self.update()
            
            # Start Fade Out
            QTimer.singleShot(200, self.start_fade_out)
        
        self.update()
        
    def start_fade_out(self):
        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setDuration(500)
        self.fade_anim.setStartValue(1.0)
        self.fade_anim.setEndValue(0.0)
        self.fade_anim.finished.connect(self.close_and_notify)
        self.fade_anim.start()
        
    def close_and_notify(self):
        self.close()
        self.finished.emit()
        
        self.update()
            
    def update_progress(self, val, text=None):
        if text: self.loading_text = text.upper()
        # Only process events if we aren't overwhelming the loop
        if not hasattr(self, '_last_evt_time'): self._last_evt_time = 0
        now = time.time()
        if now - self._last_evt_time > 0.032: # 30 FPS throttle for events
            QApplication.processEvents()
            self._last_evt_time = now
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        cx, cy = rect.width() / 2, rect.height() / 2
        painter.translate(cx, cy)
        
        # Battery Dimensions
        bat_w = 200
        bat_h = 100
        nub_w = 15
        nub_h = 40
        
        # Determine Color based on charge
        if self.charge_val < 20:
            c_charge = QColor(255, 50, 50) # Red
        elif self.charge_val < 60:
            c_charge = QColor(255, 200, 0) # Yellow
        else:
            c_charge = QColor(0, 255, 100) # Green
            
        # Draw Battery Body Outline
        painter.setPen(QPen(QColor(255, 255, 255), 4))
        painter.setBrush(QColor(0, 0, 0, 150))
        body_rect = QRectF(-bat_w/2, -bat_h/2, bat_w, bat_h)
        painter.drawRoundedRect(body_rect, 10, 10)
        
        # Draw Positive Terminal Nub
        nub_rect = QRectF(bat_w/2, -nub_h/2, nub_w, nub_h)
        painter.setBrush(QColor(255, 255, 255))
        painter.drawRoundedRect(nub_rect, 4, 4)
        
        # Draw Charge Fill
        # Inner padding
        pad = 8
        fill_max_w = bat_w - (pad * 2)
        fill_h = bat_h - (pad * 2)
        
        current_fill_w = fill_max_w * (self.charge_val / 100.0)
        
        fill_rect = QRectF(-bat_w/2 + pad, -bat_h/2 + pad, current_fill_w, fill_h)
        
        # Gradient for the fill (making it look like liquid/energy)
        grad = QLinearGradient(fill_rect.topLeft(), fill_rect.bottomLeft())
        grad.setColorAt(0, c_charge.lighter(130))
        grad.setColorAt(0.5, c_charge)
        grad.setColorAt(1, c_charge.darker(110))
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(grad)
        painter.drawRoundedRect(fill_rect, 4, 4)
        
        # Draw Lightning Bolt or Charging Icon inside if charging
        if not self.finished:
             # Pulsing overlay
             c_pulse = QColor(255, 255, 255, int(50 * self.pulse_alpha))
             painter.setBrush(c_pulse)
             painter.drawRoundedRect(fill_rect, 4, 4)
        
        # Text Percentage
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Segoe UI", 24, QFont.Weight.Bold)
        painter.setFont(font)
        
        txt = f"{int(self.charge_val)}%"
        painter.drawText(body_rect, Qt.AlignmentFlag.AlignCenter, txt)
        
        # Status Text below
        font_sub = QFont("Consolas", 10)
        painter.setFont(font_sub)
        painter.setPen(QColor(200, 200, 200))
        painter.drawText(QRectF(-bat_w, bat_h/2 + 10, bat_w*2, 30), Qt.AlignmentFlag.AlignCenter, self.loading_text)



class SparklineWidget(QWidget):
    """
    Minimalist glowing line graph for financial cards.
    """
    def __init__(self, color=COLOR_ACCENT_CYAN, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.points = [random.uniform(0.3, 0.7) for _ in range(12)]
        self.setFixedHeight(30)
        
        # Ambient pulse animation
        self.pulse = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_pulse)
        self.timer.start(100)

    def update_pulse(self):
        self.pulse = (self.pulse + 0.1) % (math.pi * 2)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        p_alpha = int(180 + 75 * math.sin(self.pulse))
        p_color = QColor(self.color)
        p_color.setAlpha(p_alpha)
        
        pen = QPen(p_color, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        w, h = self.width(), self.height()
        path = QPainterPath()
        
        step = w / (len(self.points) - 1)
        for i, val in enumerate(self.points):
            x = i * step
            y = h - (val * h)
            if i == 0: path.moveTo(x, y)
            else: path.lineTo(x, y)
            
        painter.drawPath(path)
        
        # Gradient Fill below
        grad = QLinearGradient(0, 0, 0, h)
        fill_c = QColor(p_color)
        fill_c.setAlpha(40)
        grad.setColorAt(0, fill_c)
        grad.setColorAt(1, Qt.GlobalColor.transparent)
        
        fill_path = QPainterPath(path)
        fill_path.lineTo(w, h)
        fill_path.lineTo(0, h)
        fill_path.closeSubpath()
        painter.fillPath(fill_path, grad)

class ReactorStatCard(QWidget):
    """
    A futuristic Stat Card with a rotating 'Arc Reactor' ring around the value.
    Replaces static stat cards with something alive.
    """
    def __init__(self, title, value, color=COLOR_ACCENT_CYAN, parent=None, small=False):
        super().__init__(parent)
        self.title = title
        self.value = value
        self.color = QColor(color)
        self.small = small
        
        # Dimensions
        self.setFixedSize(160, 160) if not small else self.setFixedSize(120, 100)
        
        # Adjust size based on mode
        r_outer = 60 if not self.small else 35
        r_inner = 45 if not self.small else 25

        self.angle_outer = 0
        self.angle_inner = 0
        
        # Particles
        self.particles = []
        for _ in range(15):
            self.particles.append({
                'angle': random.uniform(0, 360),
                'speed': random.uniform(1, 3),
                'dist': random.uniform(r_inner, r_outer),
                'size': random.uniform(1, 3),
                'alpha': random.randint(100, 255)
            })
        
        # Timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(30) # High refresh for particles
        
    def update_animation(self):
        self.angle_outer = (self.angle_outer + 1.5) % 360
        self.angle_inner = (self.angle_inner - 2.5) % 360
        
        # Update particles
        for p in self.particles:
            p['angle'] = (p['angle'] + p['speed']) % 360
            
        self.update() 
        
    def set_value(self, val):
        self.value = str(val)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        center = QPointF(cx, cy)
        
        # Adjust size based on mode
        r_outer = 60 if not self.small else 35
        r_inner = 45 if not self.small else 25
        
        # 1. Background Glow (Intense Plasma)
        radial = QRadialGradient(center, r_outer + 30)
        c_glow = QColor(self.color)
        c_glow.setAlpha(60)
        radial.setColorAt(0, c_glow)
        radial.setColorAt(0.7, QColor(0,0,0,0))
        painter.setBrush(QBrush(radial))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, r_outer+30, r_outer+30)

        # 2. Outer Rotating Ring (Plasma Segments)
        painter.save()
        painter.translate(center)
        painter.rotate(self.angle_outer)
        
        pen = QPen(self.color)
        pen.setWidth(4 if not self.small else 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        # Draw 3 arcs for a more complex "Reactor" look
        for i in range(3):
            painter.drawArc(int(-r_outer), int(-r_outer), int(r_outer*2), int(r_outer*2), (i*120)*16, 80*16)
        
        painter.restore()
        
        # 3. Inner Rotating Ring (Tech Dotted)
        painter.save()
        painter.translate(center)
        painter.rotate(self.angle_inner)
        
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(pen)
        painter.drawEllipse(int(-r_inner), int(-r_inner), int(r_inner*2), int(r_inner*2))
        
        painter.restore()

        # 4. Particles (Plasma Dust)
        for p in self.particles:
            px = cx + p['dist'] * math.cos(math.radians(p['angle']))
            py = cy + p['dist'] * math.sin(math.radians(p['angle']))
            
            p_color = QColor(self.color)
            p_color.setAlpha(p['alpha'])
            painter.setBrush(p_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(px, py), p['size'], p['size'])
        
        # 5. Central Value
        painter.setPen(QColor("white"))
        font = QFont("Orbitron" if not self.small else "Segoe UI", 20 if not self.small else 14, QFont.Weight.Bold)
        painter.setFont(font)
        
        val_rect = QRectF(0, cy - 15, w, 30)
        painter.drawText(val_rect, Qt.AlignmentFlag.AlignCenter, str(self.value))
        
        # 6. Label (Bottom - Floating)
        painter.setPen(QColor("#8899aa"))
        font = QFont("Rajdhani", 10 if not self.small else 8, QFont.Weight.Bold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        painter.setFont(font)
        
        lbl_rect = QRectF(0, h - 25, w, 20)
        painter.drawText(lbl_rect, Qt.AlignmentFlag.AlignCenter, self.title.upper())

from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QLabel, QLineEdit, QTextEdit)
from PyQt6.QtCore import Qt, QTimer, QPointF, pyqtSignal

class LiveTerminal(QFrame):
    """
    High-End AI Command Terminal with holographic effects and premium design.
    """
    def __init__(self, ai_assistant=None, parent=None):
        super().__init__(parent)
        self.ai_assistant = ai_assistant
        self.setMinimumHeight(120)
        
        # Animation state for border glow
        self.glow_intensity = 0
        self.glow_direction = 1
        
        # Premium Styling with gradient border effect
        self.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(5, 10, 20, 0.95),
                    stop:0.5 rgba(10, 15, 30, 0.98),
                    stop:1 rgba(5, 10, 20, 0.95));
                border: 2px solid qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00f2ff,
                    stop:0.5 #bc13fe,
                    stop:1 #00f2ff);
                border-radius: 12px;
            }
        """)
        
        # Add glow effect
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(25)
        self.shadow.setColor(QColor(0, 242, 255, 120))
        self.shadow.setOffset(0, 0)
        self.setGraphicsEffect(self.shadow)
        
        # Magnetic Pulsing State
        self.magnetic_pulse = 0.0
        self.mag_timer = QTimer(self)
        self.mag_timer.timeout.connect(self._update_magnetic)
        self.mag_timer.start(50)

        # Typewriter state
        self.pending_logs = []
        self.current_typewriter_text = ""
        self.typewriter_timer = QTimer(self)
        self.typewriter_timer.timeout.connect(self._process_typewriter)

    def _update_magnetic(self):
        self.magnetic_pulse = (self.magnetic_pulse + 0.1) % (math.pi * 2)
        # Shift shadow and border intensity
        shift = math.sin(self.magnetic_pulse) * 10
        self.shadow.setBlurRadius(25 + shift)
        self.update()

    def _process_typewriter(self):
        if not self.pending_logs:
            self.typewriter_timer.stop()
            return
        
        log_html, log_type = self.pending_logs[0]
        # For simplicity, we'll append the whole HTML but simulate the "pop"
        # Real typewriter for HTML is complex, so we'll do a slightly faster batch append
        self.log_area.append(log_html)
        self.pending_logs.pop(0)
        
        if not self.pending_logs:
            self.typewriter_timer.stop()
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 12, 15, 12)
        self.layout.setSpacing(8)
        
        # === PREMIUM HEADER ===
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        
        # AI Icon with animation
        self.ai_icon = QLabel("◈")
        self.ai_icon.setStyleSheet("""
            color: #00f2ff;
            font-size: 20px;
            font-weight: bold;
            background: transparent;
            border: none;
        """)
        header_layout.addWidget(self.ai_icon)
        
        # Title with premium typography
        lbl_title = QLabel("AI NEXUS COMMAND INTERFACE")
        lbl_title.setStyleSheet("""
            color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #00f2ff,
                stop:0.5 #ffffff,
                stop:1 #bc13fe);
            font-family: 'Segoe UI', 'Arial';
            font-size: 12px;
            font-weight: bold;
            letter-spacing: 3px;
            background: transparent;
            border: none;
        """)
        header_layout.addWidget(lbl_title)
        
        header_layout.addStretch()
        
        # Status Indicator
        self.status_indicator = QLabel("● ONLINE")
        self.status_indicator.setStyleSheet("""
            color: #00ff88;
            font-family: 'Consolas';
            font-size: 9px;
            font-weight: bold;
            background: transparent;
            border: none;
        """)
        header_layout.addWidget(self.status_indicator)
        
        self.layout.addLayout(header_layout)
        
        # Separator line
        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 transparent,
                stop:0.5 rgba(0, 242, 255, 0.5),
                stop:1 transparent);
            border: none;
        """)
        self.layout.addWidget(separator)
        
        # === LOG DISPLAY AREA ===
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("""
            QTextEdit {
                background-color: rgba(0, 0, 0, 0.7);
                color: #00ff88;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                border: 1px solid rgba(0, 242, 255, 0.2);
                border-radius: 6px;
                padding: 8px;
                selection-background-color: rgba(0, 242, 255, 0.3);
            }
            QScrollBar:vertical {
                background: rgba(0, 0, 0, 0.3);
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 242, 255, 0.5);
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0, 242, 255, 0.8);
            }
        """)
        self.layout.addWidget(self.log_area)
        
        # === COMMAND INPUT ===
        input_container = QHBoxLayout()
        input_container.setSpacing(8)
        
        # Prompt symbol
        prompt_label = QLabel("▶")
        prompt_label.setStyleSheet("""
            color: #00f2ff;
            font-size: 14px;
            font-weight: bold;
            background: transparent;
            border: none;
        """)
        input_container.addWidget(prompt_label)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(">_")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: rgba(0, 242, 255, 0.05);
                color: #ffffff;
                font-family: 'Consolas', 'Courier New';
                font-size: 12px;
                border: none;
                border-bottom: 2px solid rgba(0, 242, 255, 0.3);
                padding: 6px 10px;
                border-radius: 4px;
            }
            QLineEdit:focus {
                background-color: rgba(0, 242, 255, 0.1);
                border-bottom: 2px solid #00f2ff;
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.3);
                font-style: italic;
            }
        """)
        self.input_field.returnPressed.connect(self.handle_input)
        input_container.addWidget(self.input_field)
        
        self.layout.addLayout(input_container)
        
        # Data
        self.logs = []
        self.max_logs = 8
        
        # Animation Timer
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.update_animations)
        self.anim_timer.start(100)  # 10 FPS for subtle animations
        
        # Auto-Add Logs Timer (disabled by default for cleaner look)
        # Uncomment if you want ambient logs
        # self.log_timer = QTimer(self)
        # self.log_timer.timeout.connect(self.add_random_log)
        # self.log_timer.start(5000)  # Every 5s
        
        # Initial Welcome Message
        self.log_area.setPlainText("[SYS] AI NEXUS initialized successfully\n[SYS] Neural pathways active. Ready for commands.\n>_ ")
        
    def update_animations(self):
        """Animate the AI icon and glow effects"""
        # Rotate AI icon symbol
        symbols = ["◈", "◇", "◆", "◈"]
        import random
        if random.random() < 0.1:  # 10% chance to change
            self.ai_icon.setText(random.choice(symbols))
    
    def add_log(self, text, log_type="INFO"):
        """Add a log entry with timestamp and type"""
        from datetime import datetime
        now = datetime.now().strftime("%H:%M:%S")
        
        # Color coding based on log type
        if log_type == "USER":
            color = "#00f2ff"
            prefix = "USER"
        elif log_type == "AI":
            color = "#bc13fe"
            prefix = "AI"
        elif log_type == "SYSTEM":
            color = "#ffaa00"
            prefix = "SYS"
        elif log_type == "ERROR":
            color = "#ff4444"
            prefix = "ERR"
        else:
            color = "#00ff88"
            prefix = "LOG"
        
        formatted_log = f'<span style="color: #666;">[{now}]</span> <span style="color: {color}; font-weight: bold;">[{prefix}]</span> <span style="color: {COLOR_ACCENT_GREEN};"> {text}</span>'
        
        self.pending_logs.append((formatted_log, log_type))
        if not self.typewriter_timer.isActive():
            self.typewriter_timer.start(50)
        
    def add_random_log(self):
        """Add ambient system logs (optional)"""
        import random
        msgs = [
            "Neural network optimization complete",
            "Quantum cache synchronized",
            "Predictive algorithms running",
            "Database integrity verified",
            "Encryption layer active",
            "Memory allocation optimized"
        ]
        self.add_log(random.choice(msgs), "SYSTEM")

    def start_streaming_log(self, log_type="AI"):
        # Process pending logs first
        while self.pending_logs:
            self._process_typewriter()
            
        from datetime import datetime
        from PyQt6.QtGui import QTextCursor, QTextCharFormat, QColor
        now = datetime.now().strftime("%H:%M:%S")
        
        cursor = self.log_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_area.setTextCursor(cursor)
        
        # New line
        self.log_area.append("") 
        
        cursor = self.log_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_area.setTextCursor(cursor)
        
        prefix_html = f'<span style="color: #666;">[{now}]</span> <span style="color: #bc13fe; font-weight: bold;">[AI]</span> '
        self.log_area.insertHtml(prefix_html)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#00ff88"))
        cursor.setCharFormat(fmt)
        self.log_area.setTextCursor(cursor)

    def _append_chunk(self, chunk):
        from PyQt6.QtGui import QTextCursor
        cursor = self.log_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_area.setTextCursor(cursor)
        self.log_area.insertPlainText(chunk)
        
        scrollbar = self.log_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def handle_input(self):
        """Process user input through AI"""
        text = self.input_field.text().strip()
        if not text:
            return
        
        # Display user command
        self.add_log(text, "USER")
        self.input_field.clear()
        
        # Process via Ollama Worker
        if self.ai_assistant:
            self.start_streaming_log("AI")
            from ai_manager import OllamaWorker
            self.ollama_worker = OllamaWorker(text)
            self.ollama_worker.chunk_received.connect(self._append_chunk)
            self.ollama_worker.error_signal.connect(lambda e: self.add_log(f"Ollama Error: {e}", "ERROR"))
            self.ollama_worker.finished_signal.connect(lambda: self._append_chunk("\n>_ "))
            self.ollama_worker.start()
        else:
            self.add_log("AI core not initialized", "ERROR")

class AINexusNode(QFrame):
    """
    Predictive Engine Display.
    Cycles through smart insights generated from real data.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(70)
        self.setStyleSheet("""
            background-color: rgba(140, 0, 255, 0.1); 
            border: 1px solid #bc13fe; 
            border-radius: 8px;
        """)
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(15, 5, 15, 5)
        self.layout.setSpacing(15)
        
        # Icon / Brain Graphic
        lbl_icon = QLabel("🧠")
        lbl_icon.setStyleSheet("font-size: 24px; background: transparent; border: none;")
        self.layout.addWidget(lbl_icon)
        
        # Content Area
        content_layout = QVBoxLayout()
        content_layout.setSpacing(2)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        lbl_title = QLabel("AI NEXUS // PREDICTIVE ENGINE")
        lbl_title.setStyleSheet("color: #bc13fe; font-size: 10px; font-weight: bold; letter-spacing: 1px; background: transparent; border: none;")
        content_layout.addWidget(lbl_title)
        
        self.lbl_insight = QLabel("Initializing neural pathways...")
        self.lbl_insight.setStyleSheet("color: white; font-size: 13px; font-style: italic; background: transparent; border: none;")
        content_layout.addWidget(self.lbl_insight)
        
        self.layout.addLayout(content_layout)
        self.layout.addStretch()
        
        # Data
        self.insights = ["System Standby..."]
        self.current_idx = 0
        
        # Timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.cycle_insight)
        self.timer.start(5000) # 5s cycle
        
    def set_insights(self, insights_list):
        if insights_list:
            self.insights = insights_list
            self.current_idx = 0
            self.update_display()
            
    def cycle_insight(self):
        if not self.insights: return
        self.current_idx = (self.current_idx + 1) % len(self.insights)
        self.update_display()
        
    def update_display(self):
        text = self.insights[self.current_idx]
        self.lbl_insight.setText(text)

class TopPerformerWidget(QFrame):
    """
    Displays a list of top performing items (e.g. Top Sales, Top Parts).
    """
    def __init__(self, title, icon_emoji="🏆", parent=None):
        super().__init__(parent)
        self.setMinimumWidth(280) 
        self.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(5, 8, 15, 0.8), stop:1 rgba(2, 4, 8, 0.6));
                border: 1px solid rgba(0, 242, 255, 0.15);
                border-radius: 10px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Header
        header_layout = QHBoxLayout()
        lbl_icon = QLabel(icon_emoji)
        lbl_icon.setStyleSheet("font-size: 18px; background: transparent; border: none;")
        
        lbl_title = QLabel(title.upper())
        lbl_title.setStyleSheet("color: #00f2ff; font-weight: bold; font-family: 'Segoe UI'; font-size: 12px; letter-spacing: 1px; background: transparent; border: none;")
        
        header_layout.addWidget(lbl_icon)
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # List Container
        self.list_layout = QVBoxLayout()
        self.list_layout.setSpacing(5)
        layout.addLayout(self.list_layout)
        layout.addStretch()
        
    def set_items(self, items):
        """
        items: list of tuples (name, value_display, optional_extra)
        """
        # Clear existing
        while self.list_layout.count():
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        if not items:
            lbl_empty = QLabel("No Data Available")
            lbl_empty.setStyleSheet("color: #666; font-style: italic; padding: 10px; background: transparent; border: none;")
            lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_layout.addWidget(lbl_empty)
            return

        for idx, item in enumerate(items[:5]): # Max 5
            name, value = item[0], item[1]
            
            row = QFrame()
            row.setStyleSheet("background: transparent; border: none;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0,0,0,0)
            
            # Rank
            lbl_rank = QLabel(f"#{idx+1}")
            lbl_rank.setFixedWidth(30)
            lbl_rank.setStyleSheet(f"color: {'#ffaa00' if idx==0 else '#888'}; font-weight: bold;")
            
            # Name
            lbl_name = QLabel(str(name))
            lbl_name.setStyleSheet("color: white; font-size: 11px;")
            # Elide if too long
            
            # Value
            lbl_val = QLabel(str(value))
            lbl_val.setStyleSheet("color: #00ff88; font-weight: bold; font-family: 'Consolas';")
            
            row_layout.addWidget(lbl_rank)
            row_layout.addWidget(lbl_name, stretch=1)
            row_layout.addWidget(lbl_val)
            
            self.list_layout.addWidget(row)


from PyQt6.QtWidgets import QStyledItemDelegate, QStyle
from PyQt6.QtCore import QSize, QRect, QTimer, QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
import time
import math
from styles import COLOR_TEXT_PRIMARY, COLOR_ACCENT_CYAN

class ProTableDelegate(QStyledItemDelegate):
    """
    Premium Glowing Outline Cell Delegate.
    Optimized for performance: Paints progress bars and tags.
    Now with visibility tracking to pause animation and save CPU.
    """
    editClicked = pyqtSignal(int)
    deleteClicked = pyqtSignal(int)
    infoClicked = pyqtSignal(int)
    selectToggled = pyqtSignal(int, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.chk_size = 18
        self.btn_width = 50
        self.btn_height = 22
        self.btn_spacing = 4
        self.parent_widget = parent
        
        # We don't need a dedicated timer for time.time() sine wave, 
        # but we DO need the table's viewport to update to see the animation.
        # Therefore, we start a timer to trigger viewport updates, BUT ONLY if visible.
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._trigger_update)
        # Assuming parent is the QTableWidget
        if self.parent_widget:
            self.anim_timer.start(30) # ~33 fps
            
    def _trigger_update(self):
        # OPTIMIZATION: Only force repaint if the parent table is actually visible
        if self.parent_widget and self.parent_widget.isVisible():
            # Check if there's actually a selected row or a low stock indicator to avoid useless repaints
            has_selection = len(self.parent_widget.selectedItems()) > 0
            # For a more robust app, you might want to only update selected rects, but viewport update is safe
            if has_selection:
                self.parent_widget.viewport().update()
        
    def sizeHint(self, option, index):
        base_size = super().sizeHint(option, index)
        data = index.data(Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, dict): return base_size
            
        col_type = data.get('type', 'generic')
        
        if col_type == 'name':
            vehicle_tags = data.get('vehicle_tags', [])
            is_new = data.get('is_new', False)
            text = str(index.data(Qt.ItemDataRole.DisplayRole))
            
            font = QFont(option.font)
            font.setPointSize(9)
            fm = QFontMetrics(font)
            w = fm.horizontalAdvance(text) + 20 
            
            if vehicle_tags:
                 badge_font = QFont(option.font)
                 badge_font.setPointSize(7)
                 badge_font.setBold(True)
                 bfm = QFontMetrics(badge_font)
                 for tag in vehicle_tags:
                     tag_w = bfm.horizontalAdvance(tag) + 12 
                     w += (tag_w + 5)
            if is_new: w += 25
            if data.get('is_edited', False): w += 40
            return QSize(int(w + 20), max(base_size.height(), 40))
            
        return QSize(base_size.width(), max(base_size.height(), 40))

    def paint(self, painter, option, index):
        if not index.isValid(): return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        data = index.data(Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, dict):
            QStyledItemDelegate.paint(self, painter, option, index)
            painter.restore()
            return

        text = index.data(Qt.ItemDataRole.DisplayRole)
        col_type = data.get('type', 'generic')
        
        rect = QRect(option.rect)
        rect.adjust(1, 1, -1, -1)
        
        is_hover = (option.state & QStyle.StateFlag.State_MouseOver)
        
        fill_color = QColor(255, 255, 255, 5)
        border_color = QColor(0, 0, 0, 0)
        text_color = QColor(COLOR_TEXT_PRIMARY)
        side_border_color = QColor(0, 0, 0, 0)
        
        is_low_stock = data.get('is_low_stock', False)
        
        if col_type == 'id':
            if is_low_stock:
                fill_color = QColor(255, 0, 0, 40)
                side_border_color = QColor(255, 0, 0, 200)
                text_color = QColor(255, 100, 100)
            else:
                fill_color = QColor(0, 68, 255, 40)
                side_border_color = QColor(0, 242, 255)
                text_color = QColor(0, 242, 255)
        
        elif col_type == 'name':
            if is_low_stock:
                fill_color = QColor(255, 0, 0, 30)
                side_border_color = QColor(255, 0, 0, 150)
                text_color = QColor(255, 150, 150)
            else:
                fill_color = QColor(0, 255, 208, 20)
                side_border_color = QColor(0, 255, 208, 100)
                text_color = QColor(255, 255, 255)

        elif col_type == 'price':
            fill_color = QColor(255, 170, 0, 20)
            side_border_color = QColor(255, 170, 0)
            text_color = QColor(255, 215, 0)

        elif col_type == 'stock':
            pass

        if is_hover:
             fill_color = fill_color.lighter(150)
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill_color)
        painter.drawRect(rect)
        
        if side_border_color.alpha() > 0:
            painter.setBrush(side_border_color)
            painter.drawRect(rect.left(), rect.top(), 3, rect.height())
            
        # --- SELECTED ROW GLOWING OUTLINE ONLY ---
        if option.state & QStyle.StateFlag.State_Selected:
             t = time.time() * 2.5
             alpha_multiplier = (math.sin(t) + 1.0) / 2.0 
             
             outline_alpha = int(100 + (155 * alpha_multiplier))
             outline_color = QColor(0, 242, 255, outline_alpha)
             
             painter.setPen(QPen(outline_color, 1))
             painter.drawLine(rect.topLeft(), rect.topRight())
             painter.drawLine(rect.bottomLeft(), rect.bottomRight())
             
             if index.column() == 0:
                 painter.drawLine(rect.topLeft(), rect.bottomLeft())
             if index.model() and index.column() == index.model().columnCount() - 1:
                 painter.drawLine(rect.topRight(), rect.bottomRight())
                 
             text_color = QColor(255, 255, 255)

        # --- CONTENT DRAWING ---
        if col_type == 'select':
            checked = data.get('checked', False)
            chk_rect = QRect(rect.center().x() - 9, rect.center().y() - 9, 18, 18)
            
            painter.setPen(QPen(QColor(COLOR_ACCENT_CYAN), 1))
            if checked:
                painter.setBrush(QColor(COLOR_ACCENT_CYAN))
                painter.drawRect(chk_rect)
                painter.setPen(QPen(Qt.GlobalColor.black, 2))
                painter.drawLine(chk_rect.left()+3, chk_rect.center().y(), chk_rect.center().x(), chk_rect.bottom()-3)
                painter.drawLine(chk_rect.center().x(), chk_rect.bottom()-3, chk_rect.right()-3, chk_rect.top()+3)
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(chk_rect)
                
        elif col_type == 'stock':
            val = int(data.get('val', 0))
            max_val = int(data.get('max_val', 100))
            ratio = min(1.0, val / max(1, max_val))
            
            bar_color = QColor(0, 255, 0)
            if val <= 5: 
                t = time.time() * 4.0 
                pulse_multiplier = (math.sin(t) + 1.0) / 2.0
                pulse_alpha = int(100 + (155 * pulse_multiplier))
                bar_color = QColor(255, 0, 0, pulse_alpha)
            
            bar_rect = QRect(rect.left() + 5, rect.top() + 8, rect.width() - 10, rect.height() - 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(30, 30, 30))
            painter.drawRect(bar_rect)
            
            prog_w = int(bar_rect.width() * ratio)
            if prog_w > 0:
                painter.setBrush(bar_color)
                painter.drawRect(bar_rect.left(), bar_rect.top(), prog_w, bar_rect.height())
                
            painter.setPen(Qt.GlobalColor.black)
            font_qty = painter.font()
            font_qty.setBold(True)
            painter.setFont(font_qty)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(val))

        elif col_type == 'actions':
            actions = data.get('actions', ['info'])
            total_w = (len(actions) * self.btn_width) + ((len(actions)-1) * self.btn_spacing)
            start_x = rect.center().x() - (total_w // 2)
            y = rect.center().y() - (self.btn_height // 2)
            
            curr_x = start_x
            for act in actions:
                color = "#ffe600" 
                if act == 'edit': color = "#00e5ff"
                elif act == 'delete': color = "#ff4444"
                
                btn_r = QRect(curr_x, y, self.btn_width, self.btn_height)
                self._draw_btn(painter, btn_r, act.upper(), color, is_hover)
                curr_x += self.btn_width + self.btn_spacing

        else:
            painter.setPen(text_color)
            font = option.font
            font.setPointSize(9)
            if col_type in ['id', 'price']: font.setBold(True)
            painter.setFont(font)
            
            vehicle_tags = data.get('vehicle_tags', [])
            is_new = data.get('is_new', False)
            is_edited = data.get('is_edited', False)
            
            if col_type == 'name':
                self._draw_name_with_tags_extended(painter, rect, text, vehicle_tags, is_new, is_edited)
            elif col_type == 'description':
                tags = [t.strip() for t in text.split(',') if t.strip()]
                if tags:
                     self._draw_tags_only(painter, rect, tags)
                else:
                     painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
            else:
                 align = Qt.AlignmentFlag.AlignCenter
                 if col_type in ['name', 'vendor', 'description']: 
                     align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                 elif col_type == 'price':
                     align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
                 
                 draw_rect = QRect(rect)
                 if col_type in ['name', 'vendor', 'description']: 
                     draw_rect.adjust(5, 0, 0, 0)
                 elif col_type == 'price':
                     draw_rect.adjust(0, 0, -5, 0)
                     
                 if col_type == 'vendor' and text:
                     v_color = self._get_vendor_color(text)
                     painter.setPen(Qt.PenStyle.NoPen)
                     painter.setBrush(QColor(v_color.red(), v_color.green(), v_color.blue(), 25))
                     fm = painter.fontMetrics()
                     t_w = fm.horizontalAdvance(text)
                     pill_rect = QRect(draw_rect.left(), draw_rect.center().y() - 10, t_w + 10, 20)
                     painter.drawRoundedRect(pill_rect, 4, 4)
                     painter.setPen(v_color)
                     
                 painter.drawText(draw_rect, align, text)

        painter.restore()

    def _get_vendor_color(self, name):
        if not name: return QColor(200, 200, 200)
        h = sum(ord(c) for c in name) * 33
        hue = h % 360
        return QColor.fromHsl(hue, 230, 180)

    def _draw_btn(self, painter, rect, text, color_hex, parent_hover):
        c = QColor(color_hex)
        painter.setPen(c)
        painter.setBrush(QColor(c.red(), c.green(), c.blue(), 20)) 
        painter.drawRoundedRect(rect, 3, 3)
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_tags_only(self, painter, rect, tags):
        x = rect.left() + 5
        y = rect.top() + 4
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        fm = painter.fontMetrics()
        
        for tag in tags:
            w = fm.horizontalAdvance(tag) + 10
            h = 16
            if x + w > rect.right(): break 
                
            tag_rect = QRect(x, y, w, h)
            h_val = sum(ord(c) for c in tag)
            hue = (h_val * 50) % 255
            tag_color = QColor.fromHsl(hue, 200, 100, 200) 
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(tag_color.red(), tag_color.green(), tag_color.blue(), 40))
            painter.drawRoundedRect(tag_rect, 4, 4)
            painter.setPen(tag_color)
            painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, tag)
            x += w + 4

    def _draw_name_with_tags_extended(self, painter, rect, text, tags, is_new, is_edited):
        fm = painter.fontMetrics()
        text_w = fm.horizontalAdvance(text)
        start_x = rect.left() + 10
        
        name_r = QRect(start_x, rect.y(), text_w, rect.height())
        painter.drawText(name_r, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        
        current_x = start_x + text_w + 10
        
        if is_new:
            badge_w = 35
            br = QRect(current_x, rect.y() + (rect.height()-16)//2, badge_w, 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 255, 0, 50))
            painter.drawRoundedRect(br, 4, 4)
            painter.setPen(QColor(0, 255, 0))
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.drawText(br, Qt.AlignmentFlag.AlignCenter, "NEW")
            current_x += badge_w + 5
            
        if is_edited:
            badge_w = 45
            br = QRect(current_x, rect.y() + (rect.height()-16)//2, badge_w, 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 229, 255, 50))
            painter.drawRoundedRect(br, 4, 4)
            painter.setPen(QColor(0, 229, 255))
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.drawText(br, Qt.AlignmentFlag.AlignCenter, "EDITED")
            current_x += badge_w + 5
        
        badge_font = QFont(painter.font())
        badge_font.setPointSize(7)
        badge_font.setBold(True)
        painter.setFont(badge_font)
        badge_fm = painter.fontMetrics()
        
        for tag in tags:
            bw = badge_fm.horizontalAdvance(tag) + 12
            kc = QColor(COLOR_ACCENT_CYAN)
            if "HONDA" in tag: kc = QColor("#ff9900")
            elif "TVS" in tag: kc = QColor("#00ff00")
            
            br = QRect(current_x, rect.y() + (rect.height()-16)//2, bw, 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(kc.red(), kc.green(), kc.blue(), 40))
            painter.drawRect(br)
            painter.setPen(kc)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(br)
            painter.drawText(br, Qt.AlignmentFlag.AlignCenter, tag)
            current_x += bw + 5

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.Type.MouseButtonRelease:
            data = index.data(Qt.ItemDataRole.UserRole)
            if data is None:
                return super().editorEvent(event, model, option, index)
            col_type = data.get('type', 'generic')
            
            if col_type == 'select':
                current = data.get('checked', False)
                self.selectToggled.emit(index.row(), not current)
                return True
                
            elif col_type == 'actions':
                actions = data.get('actions', ['info'])
                total_w = (len(actions) * self.btn_width) + ((len(actions)-1) * self.btn_spacing)
                start_x = option.rect.center().x() - (total_w // 2)
                y = option.rect.center().y() - (self.btn_height // 2)
                mx = event.pos().x()
                my = event.pos().y()
                
                if y <= my <= y + self.btn_height:
                    curr_x = start_x
                    for act in actions:
                        if curr_x <= mx <= curr_x + self.btn_width:
                            if act == 'edit': self.editClicked.emit(index.row())
                            elif act == 'delete': self.deleteClicked.emit(index.row())
                            elif act == 'info': self.infoClicked.emit(index.row())
                            return True
                        curr_x += self.btn_width + self.btn_spacing
        return False
