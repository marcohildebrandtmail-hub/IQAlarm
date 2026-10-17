"""Wait for the disposable browser harness without exposing its session token."""

import time
from urllib.error import URLError
from urllib.request import urlopen


def main() -> None:
    for _ in range(120):
        try:
            with urlopen("http://127.0.0.1:18123/iqalarm-test", timeout=2) as response:
                if response.status == 200:
                    print("Browser harness is ready")
                    return
        except (URLError, TimeoutError, OSError):
            time.sleep(0.5)
    raise SystemExit("Home Assistant browser harness did not become ready")


if __name__ == "__main__":
    main()
