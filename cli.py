import argparse
import json
import logging
import os
import subprocess
import time

from pathlib import Path
from getpass import getpass

from sharifnet import connect
from disconnect import disconnect
from status import SharifNetStatus


# ============================================================
# Configuration
# ============================================================

APP_NAME = "SharifNet"

CONFIG_DIR = Path.home() / ".config" / "sharifnet"
CONFIG_FILE = CONFIG_DIR / "config.json"

SERVICE_NAME = "sharifnet-monitor.service"

DEFAULT_CONFIG = {
    "username": "",
    "password": "",
    "auto_reconnect": False,
    "reconnect_interval": 60,
}

MIN_RECONNECT_INTERVAL = 5


# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(APP_NAME)


# ============================================================
# Terminal styling (built-in only; no external dependencies)
# ============================================================

class UI:
    enabled = os.getenv("NO_COLOR") is None and os.isatty(1)
    reset = "\033[0m"
    bold = "\033[1m"
    dim = "\033[2m"
    cyan = "\033[96m"
    green = "\033[92m"
    yellow = "\033[93m"
    white = "\033[97m"

    @classmethod
    def paint(cls, value, *styles):
        return "".join(styles) + str(value) + cls.reset if cls.enabled else str(value)

    @classmethod
    def ask(cls, prompt):
        return input(cls.paint("  " + prompt, cls.bold, cls.cyan))

    @classmethod
    def rule(cls, char="─"):
        print(cls.paint(char * 58, cls.dim))


def format_duration(seconds):
    if seconds < 60:
        return f"{seconds} seconds"
    minutes, remainder = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {remainder}s" if remainder else f"{minutes} minutes"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m" if minutes else f"{hours} hours"



# ============================================================
# Configuration Management
# ============================================================

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
        logger.warning("Invalid configuration. Using defaults.")
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


# ============================================================
# systemd Management
# ============================================================

def systemctl_user(*args, check=True):
    """
    Execute a systemctl command for the current user.
    """

    return subprocess.run(
        ["systemctl", "--user", *args],
        check=check,
        text=True,
    )


def service_available() -> bool:
    try:
        systemctl_user("status", SERVICE_NAME, check=False)
        return True

    except (FileNotFoundError, subprocess.SubprocessError):
        return False


def enable_auto_reconnect() -> None:
    """
    Enable and immediately start the systemd monitor.
    """

    config = load_config()

    if not config["username"] or not config["password"]:
        print("Please configure your credentials first.")
        return

    config["auto_reconnect"] = True
    save_config(config)

    try:
        systemctl_user("daemon-reload")
        systemctl_user("enable", "--now", SERVICE_NAME)

        print("Auto-reconnect enabled.")
        print("The systemd service is now running.")

    except subprocess.CalledProcessError as exc:
        print(f"Unable to enable service: {exc}")

    except FileNotFoundError:
        print("systemctl was not found.")


def disable_auto_reconnect() -> None:
    """
    Disable and stop the systemd monitor.
    """

    config = load_config()
    config["auto_reconnect"] = False
    save_config(config)

    try:
        systemctl_user("disable", "--now", SERVICE_NAME)
        print("Auto-reconnect disabled.")

    except subprocess.CalledProcessError as exc:
        print(f"Unable to stop service: {exc}")


def restart_monitor() -> None:
    """
    Restart the monitor if auto-reconnect is enabled.
    """

    config = load_config()

    if not config["auto_reconnect"]:
        return

    try:
        systemctl_user("restart", SERVICE_NAME)

    except subprocess.CalledProcessError as exc:
        logger.warning("Unable to restart monitor: %s", exc)


def show_service_status() -> None:
    try:
        systemctl_user("status", SERVICE_NAME, check=False)

    except Exception as exc:
        print(f"Unable to retrieve service status: {exc}")


# ============================================================
# Credentials
# ============================================================

def has_credentials() -> bool:
    config = load_config()

    return bool(
        config["username"]
        and config["password"]
    )


def set_credentials() -> None:
    print("\n--- Set Credentials ---")

    username = UI.ask("Username: ").strip()
    password = getpass("Password: ")

    if not username or not password:
        print("Username and password cannot be empty.")
        return

    config = load_config()

    config["username"] = username
    config["password"] = password

    save_config(config)

    print("Credentials updated successfully.")

    restart_monitor()


def require_credentials() -> bool:
    if has_credentials():
        return True

    print("Credentials have not been configured.")
    print("Use 'sharifnet credentials' first.")

    return False


# ============================================================
# Network Operations
# ============================================================

def get_status():
    config = load_config()

    if not require_credentials():
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


def show_status() -> None:
    print("\nChecking connection...")

    try:
        status = get_status()

        if status is None:
            return

        if status.connected:
            print("\nStatus: CONNECTED")
            print(f"  IP address        {UI.paint(status.ip, UI.bold, UI.cyan)}")

        else:
            print("\nStatus: DISCONNECTED")

    except Exception as exc:
        print(f"\nUnable to retrieve status: {exc}")


def connect_network() -> None:
    config = load_config()

    if not require_credentials():
        return

    print("\nConnecting to SharifNet...")

    try:
        connect(
            config["username"],
            config["password"],
        )

        print("Connection request completed.")
        show_status()

    except Exception as exc:
        print(f"Connection failed: {exc}")


def disconnect_network() -> None:
    config = load_config()

    if not require_credentials():
        return

    print("\nDisconnecting from SharifNet...")

    try:
        disconnect(
            config["username"],
            config["password"],
        )

        print("Successfully disconnected.")

    except Exception as exc:
        print(f"Disconnection failed: {exc}")


# ============================================================
# Auto-Reconnect Configuration
# ============================================================

def set_reconnect_interval(seconds=None) -> None:
    if seconds is None:
        config = load_config()

        print(
            f"\nCurrent interval: "
            f"{config['reconnect_interval']} seconds"
        )

        try:
            seconds = int(UI.ask("New interval (seconds): "))

        except ValueError:
            print("Please enter a valid integer.")
            return

    if seconds < MIN_RECONNECT_INTERVAL:
        print(
            f"Interval must be at least "
            f"{MIN_RECONNECT_INTERVAL} seconds."
        )
        return

    config = load_config()
    config["reconnect_interval"] = seconds

    save_config(config)

    print(f"Reconnect interval set to {seconds} seconds.")

    # The monitor reads the updated interval automatically.
    # No restart is necessary.


def toggle_auto_reconnect() -> None:
    config = load_config()

    if config["auto_reconnect"]:
        disable_auto_reconnect()
    else:
        enable_auto_reconnect()


# ============================================================
# Auto-Reconnect Daemon
# ============================================================

def run_auto_reconnect() -> None:
    """
    Background monitor managed by systemd.

    The configuration is reloaded continuously.
    """

    logger.info("SharifNet auto-reconnect daemon started.")

    while True:

        config = load_config()

        # Stop when auto-reconnect is disabled.
        if not config["auto_reconnect"]:
            logger.info("Auto-reconnect disabled. Exiting.")
            break

        username = config["username"]
        password = config["password"]

        interval = max(
            MIN_RECONNECT_INTERVAL,
            int(config["reconnect_interval"]),
        )

        if not username or not password:
            logger.warning("Credentials are not configured.")

        else:
            try:
                client = SharifNetStatus(
                    username=username,
                    password=password,
                )

                try:
                    client.authenticate()
                    status = client.get_status()

                finally:
                    client.close()

                if status.connected:
                    logger.info(
                        "Connected | IP: %s",
                        status.ip,
                    )

                else:
                    logger.warning(
                        "Disconnected. Attempting reconnection..."
                    )

                    connect(username, password)

                    logger.info("Reconnection request completed.")

            except Exception:
                logger.exception(
                    "Auto-reconnect cycle failed."
                )

        for _ in range(interval):
            time.sleep(1)

            if not load_config()["auto_reconnect"]:
                logger.info("Auto-reconnect disabled. Exiting.")
                return


# ============================================================
# Interactive Menu
# ============================================================

def show_menu() -> None:
    config = load_config()
    username = config["username"] or "Not configured"
    reconnect = (
        UI.paint("● ENABLED", UI.green, UI.bold)
        if config["auto_reconnect"]
        else UI.paint("● DISABLED", UI.yellow, UI.bold)
    )

    print()
    UI.rule("═")
    print(UI.paint("   ███████╗██╗  ██╗ █████╗ ██████╗ ██╗███████╗", UI.cyan, UI.bold))
    print(UI.paint("   ██╔════╝██║  ██║██╔══██╗██╔══██╗██║██╔════╝", UI.cyan, UI.bold))
    print(UI.paint("   ███████╗███████║███████║██████╔╝██║█████╗  ", UI.cyan, UI.bold))
    print(UI.paint("   ╚════██║██╔══██║██╔══██║██╔══██╗██║██╔══╝  ", UI.cyan, UI.bold))
    print(UI.paint("   ███████║██║  ██║██║  ██║██║  ██║██║██║     ", UI.cyan, UI.bold))
    print(UI.paint("   ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝     ", UI.cyan, UI.bold))
    print(UI.paint("                  NETWORK CLIENT", UI.dim, UI.bold))
    UI.rule("═")

    print(f"  {UI.paint('ACCOUNT', UI.dim, UI.bold)}")
    print(f"  Username          {UI.paint(username, UI.white, UI.bold)}")
    print()
    print(f"  {UI.paint('CONNECTION MANAGEMENT', UI.dim, UI.bold)}")
    print(f"  Auto-reconnect    {reconnect}")
    print(f"  Reconnect period  {UI.paint(format_duration(config['reconnect_interval']), UI.white, UI.bold)}")
    UI.rule()

    print(f"  {UI.paint('ACTIONS', UI.dim, UI.bold)}")
    actions = [
        ("1", "Connect", "Establish a SharifNet connection"),
        ("2", "Disconnect", "Close the current connection"),
        ("3", "Status", "View connection and IP details"),
        ("4", "Credentials", "Update username and password"),
        ("5", "Auto-reconnect", "Toggle automatic recovery"),
        ("6", "Reconnect interval", "Configure monitoring frequency"),
        ("7", "Daemon status", "Inspect the systemd monitor"),
    ]
    for key, label, description in actions:
        print(f"  {UI.paint(key, UI.cyan, UI.bold)}  {UI.paint(label, UI.white, UI.bold):<30} {UI.paint(description, UI.dim)}")

    UI.rule()
    print(f"  {UI.paint('0', UI.yellow, UI.bold)}  Exit")
    UI.rule("═")


def interactive_menu() -> None:
    while True:

        show_menu()

        choice = UI.ask("Select an option (0-7): ").strip()

        if choice == "1":
            connect_network()

        elif choice == "2":
            disconnect_network()

        elif choice == "3":
            show_status()

        elif choice == "4":
            set_credentials()

        elif choice == "5":
            toggle_auto_reconnect()

        elif choice == "6":
            set_reconnect_interval()

        elif choice == "7":
            show_service_status()

        elif choice == "0":
            print("\nGoodbye!")
            break

        else:
            print("\nInvalid option.")

        input("\nPress ENTER to continue...")


# ============================================================
# CLI Entry Point
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="SharifNet — modern network client and connection manager"
    )

    subparsers = parser.add_subparsers(
        dest="command",
    )

    subparsers.add_parser("menu")
    subparsers.add_parser("connect")
    subparsers.add_parser("disconnect")
    subparsers.add_parser("status")
    subparsers.add_parser("credentials")
    subparsers.add_parser("enable")
    subparsers.add_parser("disable")
    subparsers.add_parser("daemon-status")

    interval_parser = subparsers.add_parser("interval")
    interval_parser.add_argument(
        "seconds",
        type=int,
        nargs="?",
    )

    subparsers.add_parser("monitor")

    args = parser.parse_args()

    commands = {
        "connect": connect_network,
        "disconnect": disconnect_network,
        "status": show_status,
        "credentials": set_credentials,
        "enable": enable_auto_reconnect,
        "disable": disable_auto_reconnect,
        "daemon-status": show_service_status,
        "menu": interactive_menu,
        None: interactive_menu,
    }

    if args.command == "monitor":
        run_auto_reconnect()

    elif args.command == "interval":
        set_reconnect_interval(args.seconds)

    else:
        commands[args.command]()


if __name__ == "__main__":
    main()