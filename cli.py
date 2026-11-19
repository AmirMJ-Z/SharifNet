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

    username = input("Username: ").strip()
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
            print(f"IP Address: {status.ip}")

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
            seconds = int(input("New interval (seconds): "))

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

        # Check configuration every second, allowing the daemon
        # to notice changes without waiting for the full interval.
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

    print("\n")
    print("=" * 45)
    print("             SHARIFNET CLIENT")
    print("=" * 45)

    print(
        f"Username: "
        f"{config['username'] or 'Not configured'}"
    )

    print(
        "Auto-reconnect: "
        + ("ON" if config["auto_reconnect"] else "OFF")
    )

    print(
        f"Reconnect interval: "
        f"{config['reconnect_interval']} seconds"
    )

    print("-" * 45)

    print("1. Connect")
    print("2. Disconnect")
    print("3. Status")
    print("4. Set Credentials")
    print("5. Toggle Auto-Reconnect")
    print("6. Set Reconnect Interval")
    print("7. Show Daemon Status")
    print("0. Exit")

    print("=" * 45)


def interactive_menu() -> None:
    while True:

        show_menu()

        choice = input("\nSelect an option: ").strip()

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
        description="SharifNet CLI Client"
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

    # Internal command used by systemd.
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