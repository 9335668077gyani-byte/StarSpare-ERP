"""
Premium Visual Effects for Billing Page

This module adds over-the-top visual enhancements including:
- Smooth number animations
- Glowing pulse effects  
- Flash animations on updates
- Dynamic color transitions
"""

from PyQt6.QtWidgets import QLabel, QGraphicsOpacityEffect
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, pyqtProperty, QTimer, QSequentialAnimationGroup
from PyQt6.QtGui import QColor

class AnimatedLabel(QLabel):
    """Label with smooth number transition animations"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._value = 0.0
        self._target_value = 0.0
        self.animation = QPropertyAnimation(self, b"value")
        self.animation.setDuration(500)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
    def get_value(self):
        return self._value
    
    def set_value(self, val):
        self._value = val
        # Update display
        if '.' in str(val) or isinstance(val, float):
            self.setText(f"{val:.2f}")
        else:
            self.setText(str(int(val)))
    
    value = pyqtProperty(float, get_value, set_value)
    
    def animateTo(self, new_value):
        """Smoothly animate to new value"""
        if new_value != self._target_value:
            self._target_value = new_value
            self.animation.stop()
            self.animation.setStartValue(self._value)
            self.animation.setEndValue(new_value)
            self.animation.start()

class PulseEffect:
    """Add pulsing glow effect to widgets"""
    
    @staticmethod
    def pulse(widget, color_start, color_end, duration=600):
        """Create a pulse animation"""
        # Store original stylesheet
        original_style = widget.styleSheet()
        
        # Create pulse sequence
        def pulse_in():
            widget.setStyleSheet(original_style + f"""
                border: 3px solid {color_end};
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {color_end}, stop:1 {color_start});
            """)
        
        def pulse_out():
            widget.setStyleSheet(original_style)
        
        # Animate
        QTimer.singleShot(0, pulse_in)
        QTimer.singleShot(duration // 2, pulse_out)

class FlashEffect:
    """Flash effect for highlighting changes"""
    
    @staticmethod
    def flash(widget, color="#00ff00", count=2):
        """Flash widget with color"""
        original_style = widget.styleSheet()
        flash_state = [False]
        
        def toggle():
            if flash_state[0]:
                widget.setStyleSheet(original_style)
            else:
                widget.setStyleSheet(original_style + f"""
                    background-color: {color};
                    border: 2px solid {color};
                """)
            flash_state[0] = not flash_state[0]
        
        for i in range(count * 2):
            QTimer.singleShot(150 * i, toggle)
        
        # Restore original
        QTimer.singleShot(150 * count * 2, lambda: widget.setStyleSheet(original_style))

class ScalePulse:
    """Scale pulsing effect"""
    
    @staticmethod
    def pulse_scale(widget, scale_factor=1.1, duration=300):
        """Pulse by scaling"""
        original_size = widget.size()
        
        def scale_up():
            new_width = int(original_size.width() * scale_factor)
            new_height = int(original_size.height() * scale_factor)
            widget.setMinimumSize(new_width, new_height)
        
        def scale_down():
            widget.setMinimumSize(original_size)
        
        QTimer.singleShot(0, scale_up)
        QTimer.singleShot(duration, scale_down)
