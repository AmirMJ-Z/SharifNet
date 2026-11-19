import os
import logging
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup

from sharifnet import connect

BASE_URL = "https://net.sharif.ir"
LOGIN_URL = f"{BASE_URL}/en-us/user/login/"
STATUS_URL = f"{BASE_URL}/en-us/user/get_user_online_session/"

REQUEST_TIMEOUT = 10

logger = logging.getLogger(__name__)


class SharifNetStatusError(Exception):
    """Raised when connection status cannot be retrieved."""


@dataclass
class ConnectionStatus:
    connected: bool
    ip: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "connected": self.connected,
            "ip": self.ip,
        }


class SharifNetStatus:
    """Retrieve SharifNet connection status."""

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

        self.session = requests.Session()
        self.session.trust_env = False

        self.csrf = None
        self.main_csrf = None

    def _request(self, method: str, url: str, **kwargs):
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        kwargs["proxies"] = {"http": "", "https": ""}

        try:
            response = self.session.request(
                method,
                url,
                **kwargs,
            )
            response.raise_for_status()
            return response

        except requests.RequestException as exc:
            raise SharifNetStatusError(
                f"Request failed: {exc}"
            ) from exc

    def authenticate(self) -> None:
        """Authenticate with the SharifNet portal."""

        response = self._request("GET", LOGIN_URL)

        soup = BeautifulSoup(response.text, "html.parser")

        csrf_input = soup.find(
            "input",
            {"name": "csrfmiddlewaretoken"},
        )

        if not csrf_input:
            raise SharifNetStatusError(
                "CSRF token not found."
            )

        self.main_csrf = csrf_input.get("value")
        self.csrf = self.session.cookies.get("csrftoken")

        if not self.main_csrf or not self.csrf:
            raise SharifNetStatusError(
                "Invalid CSRF tokens."
            )

        payload = {
            "csrfmiddlewaretoken": self.main_csrf,
            "username": self.username,
            "password": self.password,
        }

        self._request(
            "POST",
            LOGIN_URL,
            data=payload,
        )

    def get_status(self) -> ConnectionStatus:
        """Retrieve the current online session status."""

        if not self.csrf:
            raise SharifNetStatusError(
                "Authenticate before checking connection status."
            )

        headers = {
            "X-Csrftoken": self.csrf,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{BASE_URL}/en-us/user/home/",
        }

        response = self._request(
            "GET",
            STATUS_URL,
            headers=headers,
        )

        try:
            data = response.json()
        except ValueError as exc:
            raise SharifNetStatusError(
                "Invalid status response."
            ) from exc

        if "result" not in data:
            raise SharifNetStatusError(
                "Unexpected status response format."
            )

        ip = data.get("ip")

        connected = data["result"] != [[]]

        return ConnectionStatus(
            connected=connected,
            ip=ip,
        )

    def close(self) -> None:
        self.session.close()


def get_connection_status() -> ConnectionStatus:
    """Authenticate and retrieve the current connection status."""

    username = os.getenv("SHARIFNET_USERNAME")
    password = os.getenv("SHARIFNET_PASSWORD")

    if not username or not password:
        raise ValueError(
            "SHARIFNET_USERNAME and SHARIFNET_PASSWORD "
            "must be configured."
        )

    client = SharifNetStatus(username, password)

    try:
        client.authenticate()
        return client.get_status()
    finally:
        client.close()


def ensure_connected() -> ConnectionStatus:
    """Connect to SharifNet if no active session exists."""

    status = get_connection_status()

    if status.connected:
        return status

    username = os.getenv("SHARIFNET_USERNAME")
    password = os.getenv("SHARIFNET_PASSWORD")

    connect(username, password)

    return get_connection_status()


if __name__ == "__main__":
    status = ensure_connected()

    print(status.to_dict())