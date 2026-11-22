<div align="center">

<div align="center">
  <img src="images/SharifNet University Network Logo.png" alt="SharifNet Logo" width="650">
</div>

### A smarter way to manage your Sharif University of Technology network connection.

[![Ubuntu](https://img.shields.io/badge/Ubuntu-24.04-E95420?logo=ubuntu&logoColor=white)](https://ubuntu.com/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux-FCC624?logo=linux&logoColor=black)](https://www.kernel.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/AmirMJ-Z/SharifNet?style=social)](https://github.com/AmirMJ-Z/SharifNet/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/AmirMJ-Z/SharifNet?style=social)](https://github.com/AmirMJ-Z/SharifNet/network/members)

**Connect. Monitor. Reconnect. Automatically.**

[Features](#-features) · [Installation](#-installation) · [Usage](#-usage) · [Desktop Indicator](#-desktop-indicator) · [Automatic Reconnection](#-automatic-reconnection) · [Troubleshooting](#-troubleshooting)

</div>

---

## Overview

**SharifNet** is a lightweight command-line utility designed to simplify network connection management at **Sharif University of Technology**.

Instead of manually connecting to the university network whenever your connection drops, SharifNet provides a unified CLI for managing your credentials, establishing and terminating connections, checking connection status, and automatically reconnecting when connectivity is lost.

SharifNet also integrates with **systemd user services**, allowing automatic connection monitoring to run in the background without requiring an open terminal.

Additionally, SharifNet now includes a **desktop system tray indicator** for Linux, providing convenient graphical access to connection management. You can monitor your connection status, connect or disconnect, and control automatic reconnection directly from your desktop without opening a terminal.

## Features

- **Simple CLI:** Manage your network connection directly from the terminal.
- **Credential Management:** Configure and securely store your network credentials locally.
- **Connection Management:** Connect and disconnect whenever you need.
- **Connection Monitoring:** Check your current authentication and connection status.
- **Automatic Reconnection:** Automatically reconnect when the network connection is interrupted.
- **Configurable Intervals:** Choose how frequently the connection should be checked.
- **systemd Integration:** Run the reconnection monitor as a background user service.
- **Persistent Configuration:** Keep your settings between system restarts.
- **Lightweight:** Minimal dependencies and no graphical interface required.
- **Desktop Indicator:** Manage your network connection through a convenient system tray application.
- **Graphical Controls:** Connect, disconnect, and manage automatic reconnection without using the terminal.
- **Live Status:** View your current connection and automatic reconnection status directly from the system tray.

## 📦 Installation

### Option 1: Install using a Debian package

Download the latest `.deb` package from the project's GitHub Releases page:

**[Download SharifNet Releases](https://github.com/AmirMJ-Z/SharifNet/releases)**

Install the downloaded package:

```bash
sudo apt install ./sharifnet_VERSION_all.deb
```

Replace `VERSION` with the downloaded package version.

Verify the installation:

```bash
sharifnet
```

> **Note:** An official APT repository is planned. Once available, installation and updates will be possible directly through `apt install sharifnet`.

### Option 2: Build from source

Clone the repository:

```bash
git clone https://github.com/AmirMJ-Z/SharifNet.git
cd SharifNet
```

Install the required system dependencies:

```bash
sudo apt update
sudo apt install python3 python3-requests python3-bs4 \
    debhelper devscripts dh-python
```

Build the Debian package:

```bash
dpkg-buildpackage -us -uc -b
```

The generated `.deb` package will be available in the parent directory.

Install it:

```bash
sudo apt install ../sharifnet_*_all.deb
```

> **Desktop Integration:** The Debian package also installs the SharifNet desktop indicator and its application launcher. You can find it in your desktop environment's application menu.

## Usage

SharifNet provides both an interactive interface and individual commands.

### Interactive mode

Start the interactive CLI:

```bash
sharifnet
```

Use the interactive menu to manage your connection and configuration.

### Available commands

| Command | Description |
|---|---|
| `sharifnet` | Launch the interactive CLI |
| `sharifnet connect` | Connect to the university network |
| `sharifnet disconnect` | Disconnect from the network |
| `sharifnet status` | Display the current connection status |
| `sharifnet credentials` | Configure network credentials |
| `sharifnet enable` | Enable automatic reconnection |
| `sharifnet disable` | Disable automatic reconnection |
| `sharifnet interval <seconds>` | Set the reconnection check interval |
| `sharifnet daemon-status` | Check the automatic reconnection service status |

### Examples

**Configure your credentials:**

```bash
sharifnet credentials
```

**Connect to the network:**

```bash
sharifnet connect
```

**Check connection status:**

```bash
sharifnet status
```

**Disconnect:**

```bash
sharifnet disconnect
```

**Set the monitoring interval to 30 seconds:**

```bash
sharifnet interval 30
```

## Desktop Indicator

SharifNet now includes a lightweight **system tray indicator** that provides quick access to network management directly from your Linux desktop.

Once installed, the indicator can be launched from your application menu or configured to start automatically when you log in.

Through the indicator, you can:

- **View Connection Status:** Quickly see whether you are connected to the university network.
- **Connect:** Establish a connection without opening a terminal.
- **Disconnect:** Terminate your current network connection.
- **Enable Automatic Reconnection:** Start the background monitoring service.
- **Disable Automatic Reconnection:** Stop the background monitoring service.
- **Monitor Service Status:** Check whether automatic reconnection is enabled.

### Launch the indicator

If it is not already running, launch SharifNet Indicator from your desktop application menu.

Alternatively, you can launch it from the terminal:

```bash
sharifnet-indicator
```

The indicator runs independently of the automatic reconnection service. Closing the indicator does **not** stop the background monitoring service.

There is a service behind the indicator as well, which can be enabled using `systemd`:

```bash
systemctl --user enable sharifnet-indicator.service
systemctl --user start sharifnet-indicator.service
systemctl --user status sharifnet-indicator.service
```

### Managing the background service

You can control automatic reconnection directly through the indicator:

- **Enable:** Starts the background monitoring service.
- **Disable:** Stops the background monitoring service.
- **Close:** Exits the indicator without affecting the monitoring service.

This separation allows you to close the graphical interface while keeping automatic reconnection running in the background.

> **Note:** The indicator is a graphical interface for managing SharifNet. It does not need to remain open for automatic reconnection to work.

## Automatic Reconnection

One of SharifNet's main features is its automatic reconnection mechanism.

When enabled, SharifNet runs a background monitoring service that periodically checks your network connection. If the connection is lost, it attempts to reconnect automatically.

### Enable automatic reconnection

```bash
sharifnet enable
```

This enables and starts the systemd user service.

### Disable automatic reconnection

```bash
sharifnet disable
```

### Configure the monitoring interval

For example, to check the connection every 60 seconds:

```bash
sharifnet interval 60
```

The interval is configurable according to your needs.

### Check service status

```bash
sharifnet daemon-status
```

You can also inspect the service directly using systemd:

```bash
systemctl --user status sharifnet-monitor.service
```

### View service logs

To follow the monitoring service logs in real time:

```bash
journalctl --user -u sharifnet-monitor.service -f
```

### Keep the service running after logout

By default, user services may stop when you log out. If you want the automatic reconnection service to continue running without an active login session, enable systemd lingering:

```bash
sudo loginctl enable-linger "$USER"
```

To disable lingering later:

```bash
sudo loginctl disable-linger "$USER"
```

## ⚙️ Configuration

SharifNet stores its configuration in:

```text
~/.config/sharifnet/config.json
```

The configuration includes:

| Parameter | Description |
|---|---|
| `username` | Your university network username |
| `password` | Your university network password |
| `auto_reconnect` | Enables or disables automatic reconnection |
| `reconnect_interval` | Connection monitoring interval in seconds |

Example configuration:

```json
{
    "username": "<YOUR_USERNAME>",
    "password": "<YOUR_PASSWORD>",
    "auto_reconnect": false,
    "reconnect_interval": 60
}
```

The configuration directory and file are restricted to the current user.

> **Security note:** Credentials are stored locally. Although file permissions restrict access to your user account, the password is not encrypted. Do not share your configuration file or commit it to version control.

## Troubleshooting

### The connection does not work

Check your credentials:

```bash
sharifnet credentials
```

Then try connecting again:

```bash
sharifnet connect
```

### Automatic reconnection is not working

Check whether the service is running:

```bash
systemctl --user status sharifnet-monitor.service
```

Inspect its logs:

```bash
journalctl --user -u sharifnet-monitor.service -n 100
```

If necessary, restart the service:

```bash
systemctl --user restart sharifnet-monitor.service
```

### The service does not continue after logout

Enable systemd lingering:

```bash
sudo loginctl enable-linger "$USER"
```

### Check the current configuration

```bash
cat ~/.config/sharifnet/config.json
```

Avoid sharing this output because it may contain your password.

## Technology Stack

- **Python** — Core application and CLI implementation.
- **Requests** — HTTP communication with the university network authentication service.
- **Beautiful Soup** — HTML parsing.
- **systemd** — Background monitoring and automatic reconnection.
- **Debian Packaging** — Native `.deb` distribution.
- **PySide6 (Qt):** Desktop system tray indicator and graphical controls.

## License

This project is distributed under the **MIT License**. See the [LICENSE](LICENSE) file for more information.

## ⚠️ Disclaimer

SharifNet is an independent, community-developed utility and is not officially affiliated with, endorsed by, or maintained by Sharif University of Technology.

Users are responsible for complying with the university's network usage policies. (Nobody's gonna care, tbh. Apparently, cybersecurity is the last thing we care about here.)

---

<div align="center">

[GitHub Repository](https://github.com/AmirMJ-Z/SharifNet) · [Report a Bug](https://github.com/AmirMJ-Z/SharifNet/issues) · [Request a Feature](https://github.com/AmirMJ-Z/SharifNet/issues)

</div>
