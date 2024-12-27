import sys
import time
import platform
import ctypes
import subprocess
import winreg as reg
import os

from PyQt5.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QEasingCurve, QPropertyAnimation, QSettings,  QPoint
)
from PyQt5.QtGui import (
    QIcon, QColor, QPalette, QFont
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
    QPushButton, QSlider, QHBoxLayout, QMessageBox, QSystemTrayIcon, QMenu,
    QAction, QGroupBox, QGridLayout, QProgressBar, QGraphicsDropShadowEffect,
    QGraphicsBlurEffect, QDialog, QCheckBox
)

class StartupDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Startup Options")
        self.setGeometry(400, 300, 300, 150)

        layout = QVBoxLayout()
        self.startup_checkbox = QCheckBox("Start on Windows Launch")
        self.startup_checkbox.setChecked(self.check_startup_status())

        confirm_button = QPushButton("OK")
        confirm_button.clicked.connect(self.handle_startup_choice)

        layout.addWidget(self.startup_checkbox)
        layout.addWidget(confirm_button)
        self.setLayout(layout)

    def handle_startup_choice(self):
        if self.startup_checkbox.isChecked():
            self.add_to_startup()
        else:
            self.remove_from_startup()
        self.accept()

    def check_startup_status(self):
        key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "RestTimerApp"
        try:
            with reg.OpenKey(reg.HKEY_CURRENT_USER, key, 0, reg.KEY_READ) as reg_key:
                reg.QueryValueEx(reg_key, app_name)
                return True
        except FileNotFoundError:
            return False

    def add_to_startup(self):
        exe_path = os.path.abspath(sys.argv[0])
        key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "RestTimerApp"
        with reg.OpenKey(reg.HKEY_CURRENT_USER, key, 0, reg.KEY_SET_VALUE) as reg_key:
            reg.SetValueEx(reg_key, app_name, 0, reg.REG_SZ, exe_path)

    def remove_from_startup(self):
        key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "RestTimerApp"
        try:
            with reg.OpenKey(reg.HKEY_CURRENT_USER, key, 0, reg.KEY_SET_VALUE) as reg_key:
                reg.DeleteValue(app_name)
        except FileNotFoundError:
            pass

# --------------------------------------------------
# Windows Idle Detection (Helper)
# --------------------------------------------------
class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.c_uint),
        ('dwTime', ctypes.c_ulong)
    ]

def get_idle_duration_windows():
    """
    Returns idle time on Windows in seconds.
    Reference approach using GetLastInputInfo.
    """
    lastInputInfo = LASTINPUTINFO()
    lastInputInfo.cbSize = ctypes.sizeof(lastInputInfo)
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lastInputInfo)):
        millis = ctypes.windll.kernel32.GetTickCount() - lastInputInfo.dwTime
        return millis / 1000.0
    return 0

# --------------------------------------------------
# Inactivity Detection Thread
# --------------------------------------------------
class InactivityDetectionThread(QThread):
    inactivity_detected = pyqtSignal(bool)

    def __init__(self, idle_threshold=300, parent=None):
        """
        :param idle_threshold: In seconds. 
                              If user is idle for this many seconds, emit True; 
                              else emit False.
        """
        super().__init__(parent)
        self._idle_threshold = idle_threshold
        self._running = True



    def run(self):
        while self._running:
            current_platform = platform.system()

            if current_platform == 'Windows':
                idle_seconds = get_idle_duration_windows()
                if idle_seconds >= self._idle_threshold:
                    self.inactivity_detected.emit(True)
                else:
                    self.inactivity_detected.emit(False)
            elif current_platform == 'Linux':
                # For Linux, you'd call xprintidle. Example:
                # idle_ms = int(subprocess.check_output("xprintidle"))
                # if idle_ms/1000 >= self._idle_threshold:
                #     self.inactivity_detected.emit(True)
                # else:
                #     self.inactivity_detected.emit(False)
                self.inactivity_detected.emit(False)
            else:
                # macOS or other - skip or always assume active
                self.inactivity_detected.emit(False)

            self.sleep(5)  # Check every 5 seconds

    def stop(self):
        self._running = False

# --------------------------------------------------
# Worker Thread for Timer
# --------------------------------------------------
class TimerThread(QThread):
    tick = pyqtSignal(int)          # Emit remaining seconds each tick
    phase_completed = pyqtSignal()  # Emit when work/rest phase completes
    stopped = pyqtSignal()          # Emit when the timer is manually stopped

    def __init__(self, duration, stop_event, parent=None):
        super().__init__(parent)
        self.duration = duration
        self.stop_event = stop_event

    def run(self):
        remaining = self.duration * 60  # convert minutes to seconds
        while remaining >= 0:
            if self.stop_event.is_set():
                self.stopped.emit()
                break
            self.tick.emit(remaining)
            time.sleep(1)
            remaining -= 1

        if not self.stop_event.is_set():
            # Phase completed normally
            self.phase_completed.emit()

# --------------------------------------------------
# Rest Popup Window
# --------------------------------------------------
class RestPopup(QWidget):
    def __init__(self, rest_duration, parent=None):
        super().__init__(parent)
        self.rest_duration = rest_duration
        self.initUI()

    def initUI(self):
        # Make the popup full screen
        self.resize(800, 600)  # Width: 800, Height: 600
        
        # Set window flags to stay on top and disable interaction with underlying windows
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )

        # Semi-transparent background
        self.setWindowOpacity(0.9)
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(0, 0, 0, 160))  # Semi-transparent black
        self.setPalette(palette)
        self.setAutoFillBackground(True)

        # Layout
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Rest Message
        message = QLabel("Time to Rest!", self)
        message.setAlignment(Qt.AlignCenter)
        message.setStyleSheet("""
            color: white;
            font-size: 48px;
            font-weight: bold;
        """)

        # Countdown Label
        self.countdown_label = QLabel(self.format_time(self.rest_duration * 60), self)
        self.countdown_label.setAlignment(Qt.AlignCenter)
        self.countdown_label.setStyleSheet("""
            color: white;
            font-size: 36px;
        """)

        layout.addStretch()
        layout.addWidget(message)
        layout.addWidget(self.countdown_label)
        layout.addStretch()

        # Timer to update countdown
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_countdown)
        self.timer.start(1000)  # Update every second

        self.remaining_seconds = self.rest_duration * 60

    def format_time(self, seconds):
        minutes, secs = divmod(seconds, 60)
        return f"{minutes:02}:{secs:02}"

    def update_countdown(self):
        self.remaining_seconds -= 1
        if self.remaining_seconds >= 0:
            self.countdown_label.setText(self.format_time(self.remaining_seconds))
        else:
            self.timer.stop()
            self.close()  # Close the popup when rest time is over

    def keyPressEvent(self, event):
        # Disable key presses to prevent closing
        pass

    def mousePressEvent(self, event):
        # Disable mouse clicks to prevent closing
        pass

# --------------------------------------------------
# Main Application Window
# --------------------------------------------------
class RestTimerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rest Timer")
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        self.setWindowIcon(QIcon(icon_path))

        self.setGeometry(100, 100, 480, 340)

        # Load settings
        self.settings = QSettings("RestTimerApp", "Settings")
        self.stop_disabled = self.settings.value("stop_disabled", False, type=bool)

        # Default durations (load saved values or use defaults)
        self.work_duration = self.settings.value("work_duration", 25, type=int)
        self.rest_duration = self.settings.value("rest_duration", 5, type=int)

        # Timer states
        self.is_work_phase = True
        self.timer_running = False

        # Gamification tracking
        self.consecutive_cycles = 0  # Tracks completed work+rest cycles
        self.completed_cycles_today = 0

        # Event-like object to stop threads
        from threading import Event
        self.stop_event = Event()
        self.timer_thread = None

        # Initialize inactivity detection
        self.idle_thread = InactivityDetectionThread(idle_threshold=300)
        self.idle_thread.inactivity_detected.connect(self.handle_inactivity)
        self.idle_thread.start()

        # Configure window appearance
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)

        # Setup UI
        self.setup_global_styles()
        self.initUI()

        # Apply visual effects
        self.apply_fluent_effects()

        # Create system tray icon
        self.createTrayIcon()
        self.tray_icon.show()

        # Initialize Rest Popup (hidden initially)
        self.rest_popup = None

        # Start the timer upon launch
        self.start_timer()


    # -----------------------------------------------
    # Global Stylesheet (Fluent-Inspired)
    # -----------------------------------------------
    def setup_global_styles(self):
        """
        A modern stylesheet emphasizing Fluent Design cues:
        - Semi-transparent backgrounds
        - Soft hover states
        - Rounded corners
        - Minimalist typography
        """
        # Use Segoe UI if available (Windows default). Otherwise, fallback to sans-serif.
        font_family = "Segoe UI, sans-serif"
        self.setStyleSheet(f"""
            * {{
                font-family: "{font_family}";
                color: #333;
            }}
            QMainWindow {{
                background-color: transparent; /* We'll simulate acrylic via effects. */
            }}
            /* Container that holds everything */
            QWidget#CentralWidget {{
                background-color: rgba(255, 255, 255, 180);
                border-radius: 12px;
            }}
            QLabel#TitleLabel {{
                font-size: 24px;
                font-weight: 600;
                color: #222;
            }}
            QLabel#TimerLabel {{
                font-size: 32px;
                font-weight: bold;
            }}
            QLabel#PhaseLabel {{
                font-size: 16px;
                font-weight: 500;
            }}
            QGroupBox {{
                background-color: rgba(255, 255, 255, 160);
                border: 1px solid rgba(0,0,0,0.05);
                border-radius: 8px;
                margin-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 5px 10px;
            }}
            /* Buttons */
            QPushButton {{
                background-color: #0078d4; /* Fluent accent color (blue) */
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                margin: 4px;
            }}
            QPushButton:hover {{
                background-color: #006cbe; 
            }}
            QPushButton:pressed {{
                background-color: #005c9c;
            }}
            QPushButton#DangerButton {{
                background-color: #d83b01; /* Red accent */
            }}
            QPushButton#DangerButton:hover {{
                background-color: #c13200;
            }}
            QPushButton#DangerButton:pressed {{
                background-color: #9f2a00;
            }}

            /* Sliders */
            QSlider::groove:horizontal {{
                height: 6px;
                background: #ccc;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: #0078d4;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }}
            /* ProgressBar */
            QProgressBar {{
                border: 1px solid #ccc;
                border-radius: 6px;
                background-color: rgba(255, 255, 255, 120);
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: #0078d4;
                border-radius: 6px;
            }}
        """)

    # -----------------------------------------------
    # Apply Fluent Effects (Shadow + Blur)
    # -----------------------------------------------
    def apply_fluent_effects(self):
        """
        Simulate an acrylic-like effect on the main widget:
        1) Drop shadow around the central card
        2) Slight blur or background behind the card
        """
        # Drop shadow around the main window or central widget
        shadow_effect = QGraphicsDropShadowEffect(self)
        shadow_effect.setBlurRadius(20)
        shadow_effect.setOffset(0, 4)

        # Apply shadow to the central widget
        self.central_widget.setGraphicsEffect(shadow_effect)

    def center_window(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)


    # -----------------------------------------------
    # UI Initialization
    # -----------------------------------------------
    def initUI(self):
        # Main widget (central card) and layout
        self.central_widget = QWidget()
        self.central_widget.setObjectName("CentralWidget")
        main_layout = QVBoxLayout()
        self.central_widget.setLayout(main_layout)
        self.setCentralWidget(self.central_widget)

        # Title
        self.title_label = QLabel("Rest Timer", self)
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.title_label)

        # Timer display (with progress)
        timer_group = QGroupBox("Timer")
        timer_layout = QVBoxLayout(timer_group)
        timer_group.setLayout(timer_layout)

        self.countdown_label = QLabel("--:--", self)
        self.countdown_label.setObjectName("TimerLabel")
        self.countdown_label.setAlignment(Qt.AlignCenter)

        self.phase_label = QLabel("Work Phase", self)
        self.phase_label.setObjectName("PhaseLabel")
        self.phase_label.setAlignment(Qt.AlignCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setMinimum(0)

        timer_layout.addWidget(self.countdown_label)
        timer_layout.addWidget(self.phase_label)
        timer_layout.addWidget(self.progress_bar)
        main_layout.addWidget(timer_group)

        # Sliders Section
        sliders_group = QGroupBox("Durations (in minutes)")
        sliders_layout = QGridLayout()
        sliders_group.setLayout(sliders_layout)

        # Work Slider + Label
        lbl_work = QLabel("Work:")
        self.work_slider = QSlider(Qt.Horizontal)
        self.work_slider.setRange(1, 480)
        self.work_slider.setValue(self.work_duration)
        self.work_slider.valueChanged.connect(self.update_work_duration)

        self.work_value_label = QLabel(f"{self.work_duration} min")
        self.work_value_label.setAlignment(Qt.AlignCenter)

        sliders_layout.addWidget(lbl_work, 0, 0, 1, 2)
        sliders_layout.addWidget(self.work_value_label, 1, 0, 1, 2)  # Above slider
        sliders_layout.addWidget(self.work_slider, 2, 0, 1, 2)

        # Rest Slider + Label
        lbl_rest = QLabel("Rest:")
        self.rest_slider = QSlider(Qt.Horizontal)
        self.rest_slider.setRange(1, 60)
        self.rest_slider.setValue(self.rest_duration)
        self.rest_slider.valueChanged.connect(self.update_rest_duration)

        self.rest_value_label = QLabel(f"{self.rest_duration} min")
        self.rest_value_label.setAlignment(Qt.AlignCenter)

        sliders_layout.addWidget(lbl_rest, 3, 0, 1, 2)
        sliders_layout.addWidget(self.rest_value_label, 4, 0, 1, 2)  # Above slider
        sliders_layout.addWidget(self.rest_slider, 5, 0, 1, 2)

        main_layout.addWidget(sliders_group)


        # Buttons layout
        buttons_group = QGroupBox("Controls")
        btn_layout = QHBoxLayout()
        buttons_group.setLayout(btn_layout)

        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.start_timer)
        btn_layout.addWidget(self.start_btn)

        self.restart_btn = QPushButton("Restart")
        self.restart_btn.clicked.connect(self.restart_timer)
        btn_layout.addWidget(self.restart_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_timer)
        btn_layout.addWidget(self.stop_btn)

        self.delete_stop_btn = QPushButton("Delete Stop")
        self.delete_stop_btn.setObjectName("DangerButton")
        self.delete_stop_btn.clicked.connect(self.delete_stop_timer)
        btn_layout.addWidget(self.delete_stop_btn)

        self.hide_btn = QPushButton("Hide UI")
        self.hide_btn.clicked.connect(self.hide)
        btn_layout.addWidget(self.hide_btn)

        main_layout.addWidget(buttons_group)
        self.center_window()  # Center the window after initializing the UI

    # -----------------------------------------------
    # Tray Icon Creation
    # -----------------------------------------------
    def createTrayIcon(self):
        self.tray_icon = QSystemTrayIcon(self)
        # Replace with a valid icon path or system theme icon
        self.tray_icon.setIcon(QIcon("icon.png"))

        self.tray_menu = QMenu(self)

        self.show_action = QAction("Show Window", self)
        self.show_action.triggered.connect(self.show)
        self.tray_menu.addAction(self.show_action)

        self.stop_action = QAction("Stop Timer", self)
        self.stop_action.triggered.connect(self.stop_timer)
        self.tray_menu.addAction(self.stop_action)

        self.restart_action = QAction("Restart Timer", self)
        self.restart_action.triggered.connect(self.restart_timer)
        self.tray_menu.addAction(self.restart_action)

        self.quit_action = QAction("Quit", self)
        self.quit_action.triggered.connect(self.quit_application)
        self.tray_menu.addAction(self.quit_action)

        self.tray_icon.setContextMenu(self.tray_menu)

    def update_tray_menu(self):
        """ Update tray menu if the user deleted the Stop button permanently. """
        self.tray_menu.clear()

        self.tray_menu.addAction(self.show_action)
        if not self.stop_disabled:
            self.tray_menu.addAction(self.stop_action)
        self.tray_menu.addAction(self.restart_action)
        self.tray_menu.addAction(self.quit_action)

    # -----------------------------------------------
    # Timer Control Methods
    # -----------------------------------------------
    def start_timer(self):
        if self.timer_running:
            return

        self.stop_event.clear()
        self.timer_running = True

        duration = self.work_duration if self.is_work_phase else self.rest_duration
        self.timer_thread = TimerThread(duration, self.stop_event)
        self.timer_thread.tick.connect(self.update_timer_display)
        self.timer_thread.phase_completed.connect(self.handle_phase_completion)
        self.timer_thread.stopped.connect(self.handle_stop)
        self.timer_thread.start()

        self.progress_bar.setMaximum(duration * 60)
        self.progress_bar.setValue(duration * 60)

        self.update_phase_label()
        self.smooth_color_transition()

    def stop_timer(self):
        if not self.timer_running:
            return
        self.stop_event.set()
        self.timer_running = False

    def restart_timer(self):
        """Restart the entire cycle from Work phase."""
        self.stop_timer()   # stop current
        self.is_work_phase = True
        self.start_timer()  # start fresh

    # -----------------------------------------------
    # Timer Callbacks
    # -----------------------------------------------
    def update_timer_display(self, remaining_seconds):
        minutes, seconds = divmod(remaining_seconds, 60)
        self.countdown_label.setText(f"{minutes:02}:{seconds:02}")
        self.progress_bar.setValue(remaining_seconds)

    def handle_phase_completion(self):
        self.is_work_phase = not self.is_work_phase
        self.timer_running = False

        # If we just finished rest, a full cycle is complete
        if self.is_work_phase:
            self.consecutive_cycles += 1
            self.completed_cycles_today += 1
            self.check_achievements()

        self.show_phase_notification()
        self.start_timer()

    def handle_stop(self):
        # Timer was manually stopped
        self.timer_running = False
        self.countdown_label.setText("--:--")
        self.progress_bar.setValue(0)

    def update_phase_label(self):
        if self.is_work_phase:
            self.phase_label.setText("Work Phase")
            self.phase_label.setStyleSheet("color: #d83b01;")  # a warm accent (orange/red)
        else:
            self.phase_label.setText("Rest Phase")
            self.phase_label.setStyleSheet("color: #107c10;")  # a green accent

    def show_phase_notification(self):
        if self.is_work_phase:
            # Closed the popup if it exists
            if self.rest_popup and self.rest_popup.isVisible():
                self.rest_popup.close()

            QMessageBox.information(self, "Work Phase", "Break time is over! Back to work.")
        else:
            # Show the rest popup
            self.rest_popup = RestPopup(self.rest_duration)
            self.rest_popup.show()

    # -----------------------------------------------
    # Smooth Color Transition (Dynamic Timer)
    # -----------------------------------------------
    def smooth_color_transition(self):
        """
        Example of a minimal color transition on the phase_label.
        You could also animate the entire background or the progress bar color.
        """
        start_color = QColor("#107c10") if self.is_work_phase else QColor("#d83b01")
        end_color = QColor("#d83b01") if self.is_work_phase else QColor("#107c10")

        self.color_animation = QPropertyAnimation(self.phase_label, b"styleSheet")
        self.color_animation.setDuration(700)
        self.color_animation.setStartValue(f"color: {start_color.name()};")
        self.color_animation.setEndValue(f"color: {end_color.name()};")
        self.color_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.color_animation.start()

    # -----------------------------------------------
    # Sliders / UI Controls
    # -----------------------------------------------
    def update_work_duration(self):
        self.work_duration = self.work_slider.value()
        self.work_value_label.setText(f"{self.work_duration} min")  # Update label
        self.settings.setValue("work_duration", self.work_duration)

    def update_rest_duration(self):
        self.rest_duration = self.rest_slider.value()
        self.rest_value_label.setText(f"{self.rest_duration} min")  # Update label
        self.settings.setValue("rest_duration", self.rest_duration)


    # -----------------------------------------------
    # Stop Button Deletion
    # -----------------------------------------------
    def delete_stop_timer(self):
        reply = QMessageBox.question(
            self, "Confirm Deletion",
            "Are you sure you want to delete the stop timer permanently?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.stop_disabled = True
            self.stop_btn.hide()
            self.settings.setValue("stop_disabled", True)  # Save to QSettings
            self.update_tray_menu()

    # -----------------------------------------------
    # Inactivity Handling
    # -----------------------------------------------
    def handle_inactivity(self, inactive):
        if inactive and self.timer_running:
            print("User inactive: resetting timer.")
            self.restart_timer()

    # -----------------------------------------------
    # Gamification: Streaks & Achievements
    # -----------------------------------------------
    def check_achievements(self):
        if self.consecutive_cycles in [10, 50, 100]:
            QMessageBox.information(
                self,
                "Achievement Unlocked!",
                f"You've completed {self.consecutive_cycles} consecutive cycles! 🔥"
            )

    # -----------------------------------------------
    # Application Lifecycle
    # -----------------------------------------------
    def closeEvent(self, event):
        """Override the close event to minimize instead of exiting."""
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Rest Timer",
            "The app is still running in the background.",
            QSystemTrayIcon.Information,
            2000
        )

    def quit_application(self):
        """Stop threads and quit the app entirely."""
        if self.timer_thread and self.timer_thread.isRunning():
            self.stop_event.set()
            self.timer_thread.quit()
            self.timer_thread.wait()

        if self.idle_thread and self.idle_thread.isRunning():
            self.idle_thread.stop()
            self.idle_thread.wait()

        # Close the rest popup if it's open
        if self.rest_popup and self.rest_popup.isVisible():
            self.rest_popup.close()

        QApplication.instance().quit()

# --------------------------------------------------
# Run the Application
# --------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Check if already set to startup
    if not StartupDialog().check_startup_status():  # Only show if not set to startup
        dialog = StartupDialog()
        if dialog.exec_() != QDialog.Accepted:
            sys.exit(0)  # Exit if user cancels dialog

    window = RestTimerApp()
    window.show()

    sys.exit(app.exec_())
