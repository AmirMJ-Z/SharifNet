import os
import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://net.sharif.ir"
LOGIN_URL = f"{BASE_URL}/en-us/user/login/"
DISCONNECT_URL = f"{BASE_URL}/en-us/user/aaa_ras_disconnect/"

REQUEST_TIMEOUT = 10
MAX_RETRIES = 5

logger = logging.getLogger(__name__)


class SharifNetDisconnectError(Exception):
    """Raised when SharifNet disconnection fails."""


class SharifNetDisconnector:
    """Handles SharifNet authentication and disconnection."""

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
        kwargs.setdefault("timeout", self.timeout)
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
            raise SharifNetDisconnectError(
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
            raise SharifNetDisconnectError(
                "CSRF token not found."
            )

        self.main_csrf = csrf_input.get("value")
        self.csrf = self.session.cookies.get("csrftoken")

        if not self.main_csrf or not self.csrf:
            raise SharifNetDisconnectError(
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

    def disconnect(self) -> bool:
        """Terminate the active SharifNet session."""

        if not self.csrf:
            raise SharifNetDisconnectError(
                "Authenticate before disconnecting."
            )

        headers = {
            "X-Csrftoken": self.csrf,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{BASE_URL}/en-us/user/home/",
        }

        payload = {
            "user": self.username,
            "pass": self.password,
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._request(
                    "POST",
                    DISCONNECT_URL,
                    data=payload,
                    headers=headers,
                )

                result = response.json()

                if result.get("error") is None:
                    logger.info("Successfully disconnected from SharifNet.")
                    return True

                logger.warning(
                    "Disconnection attempt %s/%s failed: %s",
                    attempt,
                    self.max_retries,
                    result.get("error"),
                )

            except (SharifNetDisconnectError, ValueError) as exc:
                logger.warning(
                    "Disconnection attempt %s/%s failed: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )

        raise SharifNetDisconnectError(
            f"Unable to disconnect after {self.max_retries} attempts."
        )

    def close(self) -> None:
        self.session.close()


def disconnect(
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> bool:
    """Disconnect from SharifNet."""

    username = username or os.getenv("SHARIFNET_USERNAME")
    password = password or os.getenv("SHARIFNET_PASSWORD")

    if not username or not password:
        raise ValueError(
            "SHARIFNET_USERNAME and SHARIFNET_PASSWORD "
            "must be configured."
        )

    client = SharifNetDisconnector(username, password)

    try:
        client.authenticate()
        return client.disconnect()
    finally:
        client.close()


if __name__ == "__main__":
    disconnect()