import sys
from pathlib import Path

try:
    from PySide6.QtWidgets import (
        QApplication,
        QSystemTrayIcon,
        QMenu,
        QWidget,
        QLabel,
        QVBoxLayout,
        QProgressBar,
        QWidgetAction
    )
    from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor
    from PySide6.QtCore import QTimer, Qt

except ImportError:
    from PySide2.QtWidgets import (
        QApplication,
        QSystemTrayIcon,
        QMenu,
        QWidget,
        QLabel,
        QVBoxLayout,
        QAction,
        QProgressBar,
        QWidgetAction
    )
    from PySide2.QtGui import QIcon, QPixmap, QPainter, QColor
    from PySide2.QtCore import QTimer, Qt

import os
import json
import subprocess

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.sharifnet import connect
from core.disconnect import disconnect
from core.status import SharifNetStatus

DEFAULT_CONFIG = {
    "username": "",
    "password": "",
    "auto_reconnect": False,
    "reconnect_interval": 60,
}

CONFIG_DIR = Path.home() / ".config" / "sharifnet"
CONFIG_FILE = CONFIG_DIR / "config.json"

SERVICE_NAME = "sharifnet-monitor.service"

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

LOOP_INTERVAL = 2500

#===============================================================

TOTAL_VOLUME_GB = 30
PERCENTAGE_MODE = False

GREEN = "#13d571"
YELLOW = "#e6a70e"
RED = "#ca0d0d"
GRAY = "#99a0af"

REMAINING_VOLUME = 0

def load_config() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)

    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE, "r") as file:
            config = json.load(file)

        return {**DEFAULT_CONFIG, **config}

    except (json.JSONDecodeError, OSError):
        return DEFAULT_CONFIG.copy()

def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)

    temp_file = CONFIG_FILE.with_suffix(".tmp")

    fd = os.open(
        temp_file,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )

    with os.fdopen(fd, "w") as file:
        json.dump(config, file, indent=4)
        file.flush()
        os.fsync(file.fileno())

    os.replace(temp_file, CONFIG_FILE)
    os.chmod(CONFIG_FILE, 0o600)

def systemctl_user(*args, check=True):
    """
    Execute a systemctl command for the current user.
    """

    return subprocess.run(
        ["systemctl", "--user", *args],
        check=check,
        text=True,
    )

def has_credentials() -> bool:
    config = load_config()

    return bool(
        config["username"]
        and config["password"]
    )

#==========================================================

def get_status():
    config = load_config()

    if not has_credentials():
        return None

    client = SharifNetStatus(
        username=config["username"],
        password=config["password"],
    )

    try:
        client.authenticate()
        return client.get_status()

    finally:
        client.close()

#=========================================================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SharifNet")
        self.setFixedSize(400, 250)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Welcome to SharifNet!"))

class RemainingTrayApp:
    @staticmethod
    def generate_progress_image(progress: float, color: str) -> QIcon:
        width, height = 512, 150
        radius = height / 2

        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        painter.setBrush(QColor(GRAY))
        painter.drawRoundedRect(0, 0, width, height, radius, radius)

        filled_width = int(width * max(0, min(100, progress)) / 100)

        if filled_width > 0:
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(
                0, 0, filled_width, height, radius, radius
            )

        painter.end()

        return QIcon(pixmap)
class TrayApplication:
    def update_menu(self):
        global REMAINING_VOLUME

        if self.menu_is_open:
            return

        self.menu.clear()

        try:
            status = get_status()

        except Exception:
            status = None

        config = load_config()

        if config["username"]:
            self.username_indicator.setText(config["username"])
            self.menu.addAction(self.username_indicator)
            self.menu.addSeparator()

        if status is not None and status.connected:
            self.menu.addAction(self.disable_action)
            self.tray.setIcon(self.IND_CONNECTED)

        else:
            self.menu.addAction(self.enable_action)
            self.tray.setIcon(self.IND_DISCONNECTED)
            self.remaining_tray.setIcon(RemainingTrayApp.generate_progress_image(progress=0, color=GRAY))

            if config["auto_reconnect"]:
                self.menu.addAction(self.disable_auto_action)

            else:
                self.menu.addAction(self.enable_auto_action)

            self.menu.addSeparator()
            self.menu.addAction(self.exit_action)

            self.tray.setContextMenu(self.menu)
            self.remaining_tray.setContextMenu(self.menu)

            return

        if status is not None:
            remaining = status.remaining_volume
            REMAINING_VOLUME = status.remaining_volume

            self.create_remaining_display_text(remaining)

            self.menu.addAction(self.remaining_volume)

        self.menu.addSeparator()

        if config["auto_reconnect"]:
            self.menu.addAction(self.disable_auto_action)

        else:
            self.menu.addAction(self.enable_auto_action)

        self.menu.addSeparator()
        self.menu.addAction(self.exit_action)

        self.tray.setContextMenu(self.menu)
        self.remaining_tray.setContextMenu(self.menu)

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.remaining_tray = QSystemTrayIcon()
        self.remaining_tray.setToolTip("Remaining Internet Volume")

        self.remaining_tray.setIcon(
            RemainingTrayApp.generate_progress_image(0, GRAY)
        )

        self.window = MainWindow()

        self.tray = QSystemTrayIcon(None)
        self.tray.setToolTip("SharifNet")

        self.ICON_ACTIVE = QIcon(str(ASSETS_DIR / "active.png"))
        self.ICON_DEACTIVE = QIcon(str(ASSETS_DIR / "deactive.png"))
        self.ICON_CLOSE = QIcon(str(ASSETS_DIR / "close.png"))

        self.IND_CONNECTED = self.ICON_ACTIVE
        self.IND_DISCONNECTED = self.ICON_DEACTIVE

        self.REM_3 = QIcon(str(ASSETS_DIR / "remaining_3.png"))
        self.REM_2 = QIcon(str(ASSETS_DIR / "remaining_2.png"))
        self.REM_1 = QIcon(str(ASSETS_DIR / "remaining_1.png"))
        self.REM_0 = QIcon(str(ASSETS_DIR / "remaining_0.png"))

        self.USER_ICON = QIcon(str(ASSETS_DIR / "user.png"))

        self.ON_ICON = QIcon(str(ASSETS_DIR / "on.png"))
        self.OFF_ICON = QIcon(str(ASSETS_DIR / "off.png"))

        self.open_action = QAction("Open SharifNet")
        self.open_action.triggered.connect(self.show_window)
                
        self.exit_action = QAction(self.ICON_CLOSE, "Exit")
        self.exit_action.triggered.connect(self.quit)

        self.disable_action = QAction(self.ICON_ACTIVE, "Disconnect")
        self.disable_action.triggered.connect(self.disable)

        self.enable_action = QAction(self.ICON_DEACTIVE, "Connect")
        self.enable_action.triggered.connect(self.enable)

        self.enable_auto_action = QAction(self.OFF_ICON, "Enable Auto-Reconnect") 
        self.enable_auto_action.triggered.connect(self.enable_auto)

        self.disable_auto_action = QAction(self.ON_ICON, "Disable Auto-Reconnect")
        self.disable_auto_action.triggered.connect(self.disable_auto)

        self.username_indicator = QAction(self.USER_ICON, "USER")
        self.username_indicator.setEnabled(False)

        self.remaining_volume = QAction(None)
        self.remaining_volume.triggered.connect(self.switch_remaining_display)

        self.menu = QMenu()

        self.menu_is_open = False

        self.update_menu()

        self.tray.activated.connect(self.on_tray_activated)

        self.tray.show()
        self.remaining_tray.show()

        self.menu.aboutToShow.connect(
            lambda: setattr(self, "menu_is_open", True)
        )

        self.menu.aboutToHide.connect(
            lambda: setattr(self, "menu_is_open", False)
        )

        # self.tray.showMessage(
        #     "SharifNet",
        #     "Application is running in the background.",
        #     QSystemTrayIcon.MessageIcon.Information,
        #     3000,
        # )

        self.status_timer = QTimer()

        self.status_timer.timeout.connect(self.update_menu)
        self.status_timer.start(LOOP_INTERVAL)

    def switch_remaining_display(self):
        global PERCENTAGE_MODE
        global REMAINING_VOLUME

        PERCENTAGE_MODE = not PERCENTAGE_MODE
        self.create_remaining_display_text(REMAINING_VOLUME)

    def create_remaining_display_text(self, remaining: float):
        global PERCENTAGE_MODE

        if remaining >= 20:
            self.remaining_volume.setIcon(self.REM_3)
            color = GREEN
        
        elif remaining >= 10:
            self.remaining_volume.setIcon(self.REM_2)
            color = YELLOW
        
        elif remaining >= 1:
            self.remaining_volume.setIcon(self.REM_1)
            color = RED
        
        else:
            self.remaining_volume.setIcon(self.REM_0)
            color = GRAY

        percentage = int((remaining/TOTAL_VOLUME_GB) * 100)

        self.remaining_tray.setIcon(RemainingTrayApp.generate_progress_image(progress=percentage, color=color))

        if PERCENTAGE_MODE:
            self.remaining_volume.setText(f'{percentage}%')

        else:
            if remaining < 1:
                self.remaining_volume.setText(f'{remaining * 1024:.0f} MB')

            else:
                self.remaining_volume.setText(f'{remaining:.3f} GB')

    def show_window(self):
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def enable(self):
        config = load_config()
        
        if not has_credentials():
            self.tray.showMessage("SharifNet", "Failed to connect to the Sharif Network." \
            "The credientials are not set in the config file.")

            return
        
        try:
            connect(
                config["username"],
                config["password"],
            )

            # self.tray.showMessage("SharifNet", "Connected Succesfully.")
            self.update_menu()
        
        except Exception as exc:
            self.tray.showMessage("SharifNet", "An error ocurred while trying to connect to the Sharif Network:" \
                                               f"{exc}")
        

    def disable(self):
        config = load_config()
        
        if not has_credentials():
            self.tray.showMessage("SharifNet", "Failed to connect to the Sharif Network." \
                                  "The credientials are not set in the config file.")
            
            return
        
        try:
            disconnect(
                config["username"],
                config["password"],
            )

            self.update_menu()
        
        except Exception as exc:
            self.tray.showMessage("SharifNet", "An error ocurred while trying to disconnect from the Sharif Network:" \
                                                           f"{exc}")

    def enable_auto(self):
        config = load_config()
        
        if not config["username"] or not config["password"]:
            self.tray.showMessage("SharifNet", "Failed to connect to the Sharif Network." \
                                              "The credientials are not set in the config file.")
                        
            return
        
        config["auto_reconnect"] = True
        save_config(config)
        
        try:
            systemctl_user("daemon-reload")
            systemctl_user("enable", "--now", SERVICE_NAME)
            self.update_menu()
        
        except subprocess.CalledProcessError as exc:
            self.tray.showMessage("SharifNet", "Failed to enable the systemd service: " \
                                                          f"{exc}")
        
        except FileNotFoundError:
            self.tray.showMessage("SharifNet", "systemctl was not found")

    def disable_auto(self):
        config = load_config()
        config["auto_reconnect"] = False
        save_config(config)
        
        try:
            systemctl_user("disable", "--now", SERVICE_NAME)
            self.update_menu()
        
        except subprocess.CalledProcessError as exc:
            self.tray.showMessage("SharifNet", "Failed to disable the systemd service: " \
                                                                      f"{exc}") 

    def on_tray_activated(self, reason):
        # if reason in (
        #     QSystemTrayIcon.ActivationReason.Trigger,
        #     QSystemTrayIcon.ActivationReason.DoubleClick,
        # ):
        #     if self.window.isVisible():
        #         self.window.hide()

        #     else:
        #         self.show_window()

        pass

    def quit(self):
        self.tray.hide()
        self.remaining_tray.hide()
        self.app.quit()

    def run(self):
        if hasattr(self.app, "exec"):
            sys.exit(self.app.exec())
        else:
            sys.exit(self.app.exec_())

def main():
    application = TrayApplication()
    application.run()

if __name__ == "__main__":
    main()