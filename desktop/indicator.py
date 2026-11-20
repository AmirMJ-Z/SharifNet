import gi
import os
import json
from pathlib import Path
import subprocess

from sharifnet import connect
from disconnect import disconnect
from status import SharifNetStatus

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")

from gi.repository import Gtk, GLib, AyatanaAppIndicator3

CONFIG_DIR = Path.home() / ".config" / "sharifnet"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "username": "",
    "password": "",
    "auto_reconnect": False,
    "reconnect_interval": 60,
}

SERVICE_NAME = "sharifnet-monitor.service"

def has_credentials() -> bool:
    config = load_config()

    return bool(
        config["username"]
        and config["password"]
    )

def require_credentials() -> bool:
    if has_credentials():
        return True

    print("Credentials have not been configured.")
    print("Use 'sharifnet credentials' first.")

    return False

def systemctl_user(*args, check=True):
    """
    Execute a systemctl command for the current user.
    """

    return subprocess.run(
        ["systemctl", "--user", *args],
        check=check,
        text=True,
    )

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

class SharifNetIndicator:
    def __init__(self):
        self.indicator = AyatanaAppIndicator3.Indicator.new(
            "sharifnet",
            "network-transmit-receive",
            AyatanaAppIndicator3.IndicatorCategory.NETWORK
        )

        self.indicator.set_status(
            AyatanaAppIndicator3.IndicatorStatus.ACTIVE
        )

        self.build_menu()

    def show_error(self, message: str, title: str = "SharifNet Error"):
        dialog = Gtk.MessageDialog(
            transient_for=None,
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )

        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    def show_info(self, message: str, title: str = "SharifNet"):
        dialog = Gtk.MessageDialog(
            transient_for=None,
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )

        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    def build_menu(self):
        menu = Gtk.Menu()

        self.status_item = Gtk.MenuItem(
            label="Status: Checking..."
        )
        self.status_item.set_sensitive(False)

        menu.append(self.status_item)
        menu.append(Gtk.SeparatorMenuItem())

        connect = Gtk.MenuItem(label="Connect")
        connect.connect("activate", self.connect)

        menu.append(connect)

        disconnect = Gtk.MenuItem(label="Disconnect")
        disconnect.connect("activate", self.disconnect)

        menu.append(disconnect)

        menu.append(Gtk.SeparatorMenuItem())

        self.auto_reconnect = Gtk.CheckMenuItem(
            label="Auto Reconnect"
        )

        self.auto_reconnect.set_active(True)

        self.auto_reconnect.connect(
            "toggled",
            self.toggle_auto_reconnect
        )

        menu.append(self.auto_reconnect)

        menu.append(Gtk.SeparatorMenuItem())

        exit_item = Gtk.MenuItem(label="Exit")
        exit_item.connect("activate", self.exit)

        menu.append(exit_item)

        menu.show_all()

        self.indicator.set_menu(menu)

    def connect(self):
        print("Connecting to SharifNet...")

    def disconnect(self):
        print("Disconnecting from SharifNet...")

    def toggle_auto_reconnect(self, item):
        enabled = item.get_active()

        if not enabled:
            config = load_config()
            
            if not config["username"] or not config["password"]:
                self.show_error(message="Please configure your credentials first.")
                return
            
            config["auto_reconnect"] = True
            save_config(config)
            
            try:
                systemctl_user("daemon-reload")
                systemctl_user("enable", "--now", SERVICE_NAME)
            
            except subprocess.CalledProcessError as exc:
                self.show_error(message=f"Unable to enable service: {exc}")
            
            except FileNotFoundError:
                self.show_error(message="systemctl was not found.")

        else:
            config = load_config()
            config["auto_reconnect"] = False
            save_config(config)
            
            try:
                systemctl_user("disable", "--now", SERVICE_NAME)
            
            except subprocess.CalledProcessError as exc:
                self.show_error(message=f"Unable to stop service: {exc}")

    def update_status(self):
        status = False
        config = load_config()
        
        if not require_credentials():
            return None
        
        client = SharifNetStatus(
            username=config["username"],
            password=config["password"],
        )
        
        try:
            client.authenticate()
            status = client.get_status()
        
        finally:
            client.close()

        GLib.idle_add(
            self.status_item.set_label,
            f"Status: {status}"
        )

    def exit(self, _):
        Gtk.main_quit()

    def run(self):
        Gtk.main()

if __name__ == "__main__":
    app = SharifNetIndicator()
    app.run()