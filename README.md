# RestPomodoro
![image](https://github.com/user-attachments/assets/44ad5aef-8676-46e8-bf42-f8f96fdbc3f4)

**RestPomodoro** is a lightweight, distraction-free timer application designed to help you manage work and rest intervals using the Pomodoro technique. Built with PyQt5 for a sleek and minimal interface, RestPomodoro ensures that you stay productive while taking regular breaks.

---

## Features
- **Work/Rest Timer** – Set customizable work and rest durations.
- **Full-Screen Breaks** – Prevent distractions by displaying a full-screen rest popup.
- **Idle Detection** – Automatically reset the timer if inactivity is detected.
- **Startup Option** – Easily configure the app to launch on Windows startup.
- **System Tray Integration** – Control the app from the system tray for seamless background operation.
- **Fluent Design Inspired UI** – A modern and elegant interface with smooth transitions and shadows.

---

## Requirements
- **Python 3.11+**
- **PyQt5**
- **Windows 10+** (for idle detection and startup registry management)

---

## Installation
1. Clone the repository or download the ZIP.
```bash
https://github.com/yourusername/RestPomodoro.git
```

2. Navigate to the project directory:
```bash
cd RestPomodoro
```

3. Create a virtual environment (optional but recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Run the application:
```bash
python RestPomodoro.py
```

---

## Building Executable
To create a standalone executable, use PyInstaller:
```bash
pyinstaller --onefile --windowed --add-data "icon.png;." --icon=icon.ico RestPomodoro.py
```
- `--onefile` – Packages the app into a single executable.
- `--windowed` – Runs the app without opening a console window.
- `--add-data` – Ensures `icon.png` is included.
- `--icon` – Sets the taskbar and window icon.

The executable will be available in the `dist` folder.

---

## Configuration
### Startup on Windows
Upon first launch, RestPomodoro prompts you to add it to Windows startup. If you choose "Start on Windows Launch," the app registers itself under the Windows Registry at:
```
HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
```

You can disable this option from the settings dialog.

---

## Usage
1. **Start the Timer** – Adjust the work/rest slider durations and press "Start."
2. **Rest Popup** – When the work phase ends, a fullscreen popup notifies you to rest.
3. **Idle Detection** – If no activity is detected for 5 minutes, the timer resets.
4. **System Tray** – Minimize to the tray and control the timer from the tray icon.

---

## Known Issues
- **Startup Dialog Reappears** – If the app repeatedly asks to launch at startup, ensure the following fix is applied:
```python
if not StartupDialog().check_startup_status():
    dialog = StartupDialog()
    if dialog.exec_() != QDialog.Accepted:
        sys.exit(0)
```
- **Icon Not Showing in Taskbar** – Ensure `icon.png` exists and use an absolute path for the icon:
```python
icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
self.setWindowIcon(QIcon(icon_path))
```
- clicking start 2 times with different timers. Need to stop then start at the moment. 

---

## Contributing
Feel free to submit pull requests or open issues for feature requests and bug reports.

---

## License
OpenSource.

