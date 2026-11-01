#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from calculator import CalculationError, calculate_utilities


BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"


class UtilityHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            content = INDEX_FILE.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        if self.path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Страница не найдена"})

    def do_POST(self) -> None:
        if self.path != "/api/calculate":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Маршрут не найден"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Некорректный запрос"})
            return

        raw_body = self.rfile.read(length)
        try:
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Некорректный формат JSON"})
            return

        if not isinstance(payload, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Ожидался объект данных"})
            return

        try:
            result = calculate_utilities(payload)
        except CalculationError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        self._send_json(HTTPStatus.OK, result)

    def _send_json(self, status: HTTPStatus, data: dict) -> None:
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args) -> None:
        # Оставляем консоль чистой без спама на каждый запрос
        return


def pick_port(host: str, preferred_port: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex((host, preferred_port)) != 0:
            return preferred_port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Калькулятор коммунальных платежей на два дома")
    parser.add_argument("--host", default="127.0.0.1", help="Хост сервера (по умолчанию 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Предпочтительный порт (по умолчанию 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Не открывать браузер автоматически")
    args = parser.parse_args()

    port = pick_port(args.host, args.port)
    server = ThreadingHTTPServer((args.host, port), UtilityHandler)
    url = f"http://{args.host}:{port}"

    print(f"Приложение запущено: {url}")
    print("Для остановки нажмите Ctrl+C")

    if not args.no_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nСервер остановлен.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

