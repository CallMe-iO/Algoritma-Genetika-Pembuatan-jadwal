"""Helper script to start the API and open the browser."""
from __future__ import annotations

import threading
import time
import webbrowser

import uvicorn


URL = "http://127.0.0.1:8000/"


def _open_browser() -> None:
    time.sleep(1.5)
    webbrowser.open(URL)


def main() -> None:
    thread = threading.Thread(target=_open_browser, daemon=True)
    thread.start()
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
