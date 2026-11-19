import os
import subprocess
import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://net.sharif.ir"
LOGIN_URL = f"{BASE_URL}/en-us/user/login/"
CONNECT_URL = f"{BASE_URL}/en-us/user/aaa_ras_connect/"

SUPPORTED_SSIDS = {
    "Sharif-Net",
    "EEWLAN",
    "EEWLANN",
}

REQUEST_TIMEOUT = 10
MAX_RETRIES = 5

logger = logging.getLogger(__name__)


class SharifNetError(Exception):
    """Base exception for SharifNet operations."""


class AuthenticationError(SharifNetError):
    """Raised when SharifNet authentication fails."""


def get_current_ssid() -> Optional[str]:
    """Return the currently connected Wi-Fi SSID."""

    try:
        result = subprocess.run(
            ["iwgetid", "-r"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )

        return result.stdout.strip() or None

    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def is_connected_to_sharif_ssid() -> bool:
    """Check whether connected to a supported Sharif Wi-Fi network."""

    return get_current_ssid() in SUPPORTED_SSIDS


class SharifNetClient:
    """Client for Sharif University network authentication."""

    def __init__(
        self,
        username: str,
        password: str,
        timeout: int = REQUEST_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ):
        self.username = username
        self.password = password
        self.timeout = timeout
        self.max_retries = max_retries

        self.session = requests.Session()
        self.session.trust_env = False

        self.main_csrf = None
        self.csrf = None

    def _request(self, method: str, url: str, **kwargs):
        """Execute a request without using configured proxies."""

        kwargs.setdefault("timeout", self.timeout)
        kwargs["proxies"] = {"http": "", "https": ""}

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response

        except requests.RequestException as exc:
            raise SharifNetError(
                f"Request failed: {url}: {exc}"
            ) from exc

    def get_csrf_token(self) -> None:
        """Retrieve CSRF tokens required for authentication."""

        response = self._request("GET", LOGIN_URL)

        soup = BeautifulSoup(response.text, "html.parser")

        csrf_input = soup.find(
            "input",
            {"name": "csrfmiddlewaretoken"}
        )

        if not csrf_input or not csrf_input.get("value"):
            raise AuthenticationError("CSRF token not found.")

        self.main_csrf = csrf_input["value"]
        self.csrf = self.session.cookies.get("csrftoken")

        if not self.csrf:
            raise AuthenticationError("CSRF cookie not found.")

    def login(self) -> bool:
        """Authenticate and establish a SharifNet connection."""

        self.get_csrf_token()

        login_payload = {
            "csrfmiddlewaretoken": self.main_csrf,
            "username": self.username,
            "password": self.password,
        }

        self._request(
            "POST",
            LOGIN_URL,
            data=login_payload,
        )

        headers = {
            "X-Csrftoken": self.csrf,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{BASE_URL}/en-us/user/home/",
        }

        connect_payload = {
            "user": self.username,
            "pass": self.password,
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._request(
                    "POST",
                    CONNECT_URL,
                    data=connect_payload,
                    headers=headers,
                )

                result = response.json()

                if result.get("error") is None:
                    logger.info("Successfully connected to SharifNet.")
                    return True

                logger.warning(
                    "Connection attempt %s/%s failed: %s",
                    attempt,
                    self.max_retries,
                    result.get("error"),
                )

            except (SharifNetError, ValueError) as exc:
                logger.warning(
                    "Connection attempt %s/%s failed: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )

        raise AuthenticationError(
            f"Unable to establish SharifNet connection "
            f"after {self.max_retries} attempts."
        )

    def close(self) -> None:
        self.session.close()


def connect(
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> bool:
    """Connect to SharifNet using supplied or environment credentials."""

    username = username or os.getenv("SHARIFNET_USERNAME")
    password = password or os.getenv("SHARIFNET_PASSWORD")

    if not username or not password:
        raise ValueError(
            "Set SHARIFNET_USERNAME and SHARIFNET_PASSWORD."
        )

    client = SharifNetClient(username, password)

    try:
        return client.login()
    finally:
        client.close()


if __name__ == "__main__":
    if is_connected_to_sharif_ssid():
        connect()
    else:
        logger.info("Not connected to a supported Sharif SSID.")