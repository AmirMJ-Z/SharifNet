from core.sharifnet import connect
from core.disconnect import disconnect
from core.status import get_connection_status, ensure_connected


class SharifNet:
    """Unified programmatic interface for SharifNet."""

    def connect(self) -> bool:
        return connect()

    def disconnect(self) -> bool:
        return disconnect()

    def status(self):
        return get_connection_status()

    def ensure_connected(self):
        return ensure_connected()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="SharifNet client"
    )

    parser.add_argument(
        "action",
        choices=["connect", "disconnect", "status"],
    )

    args = parser.parse_args()

    client = SharifNet()

    if args.action == "connect":
        client.connect()

    elif args.action == "disconnect":
        client.disconnect()

    elif args.action == "status":
        status = client.status()
        print(status.to_dict())