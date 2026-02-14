from __future__ import annotations

import argparse
import getpass
import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _normalize_base_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "http://127.0.0.1:8000"
    return text.rstrip("/")


def _request_json(
    *,
    method: str,
    url: str,
    payload: Optional[Dict[str, Any]] = None,
    bearer_token: Optional[str] = None,
    timeout_sec: int = 15,
) -> Tuple[int, Dict[str, Any]]:
    body: Optional[bytes] = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    req = urllib.request.Request(url=url, method=method.upper(), data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            status = int(getattr(resp, "status", 200) or 200)
            data = json.loads(raw) if raw else {}
            return status, data if isinstance(data, dict) else {"raw": data}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {"detail": raw}
        if not isinstance(data, dict):
            data = {"raw": data}
        return int(exc.code), data
    except urllib.error.URLError as exc:
        return 0, {"detail": f"network_error: {exc.reason}"}


def _read_non_empty(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("Input cannot be empty.")


def _format_teacher_rows(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "(no teachers)"
    headers = [
        ("teacher_id", "Teacher ID"),
        ("teacher_name", "Name"),
        ("email", "Email"),
        ("password_set", "Pwd"),
        ("is_disabled", "Disabled"),
        ("token_version", "TV"),
    ]
    widths: List[int] = [len(title) for _, title in headers]
    rows: List[List[str]] = []
    for item in items:
        row = [
            str(item.get("teacher_id") or ""),
            str(item.get("teacher_name") or ""),
            str(item.get("email") or ""),
            "Y" if bool(item.get("password_set")) else "N",
            "Y" if bool(item.get("is_disabled")) else "N",
            str(item.get("token_version") or 0),
        ]
        rows.append(row)
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    def _line(values: List[str]) -> str:
        parts = []
        for idx, value in enumerate(values):
            parts.append(value.ljust(widths[idx]))
        return " | ".join(parts)

    title_row = _line([title for _, title in headers])
    sep = "-+-".join("-" * w for w in widths)
    body = "\n".join(_line(row) for row in rows)
    return f"{title_row}\n{sep}\n{body}"


class AdminAuthTUI:
    def __init__(
        self,
        *,
        base_url: str,
        username: Optional[str],
        password: Optional[str],
        trusted_local: bool,
    ):
        self.base_url = _normalize_base_url(base_url)
        self.username = str(username or "").strip()
        self.password = str(password or "")
        self.access_token = ""
        self.trusted_local = bool(trusted_local)
        self.local_actor_id = ""
        self._local_store = None

    def run(self) -> int:
        if self.trusted_local:
            if not self._init_local_mode():
                return 1
        else:
            print(f"Admin TUI endpoint: {self.base_url}")
            if not self._login_remote():
                return 1
        return self._menu_loop()

    def _init_local_mode(self) -> bool:
        try:
            from services.api.auth_registry_service import build_auth_registry_store

            self._local_store = build_auth_registry_store()
            result = self._local_store.bootstrap_admin()
            if result.get("ok") is not True:
                print(f"Local init failed: {result.get('error')}")
                return False
            self.local_actor_id = str(result.get("username") or os.getenv("ADMIN_USERNAME", "admin"))
            print("Trusted local mode enabled (container-level trust).")
            print(f"Active admin actor: {self.local_actor_id}")
            return True
        except Exception as exc:
            print(f"Local init failed: {exc}")
            return False

    def _login_remote(self) -> bool:
        for _ in range(3):
            username = self.username or input("Admin username: ").strip()
            if not username:
                print("Username is required.")
                continue
            password = self.password or getpass.getpass("Admin password: ")
            status, payload = _request_json(
                method="POST",
                url=f"{self.base_url}/auth/admin/login",
                payload={"username": username, "password": password},
            )
            if status == 200 and payload.get("ok") is True:
                token = str(payload.get("access_token") or "")
                if not token:
                    print("Login response missing access_token.")
                    return False
                self.access_token = token
                self.username = username
                self.password = ""
                print("Login success.")
                return True
            error = str(payload.get("error") or payload.get("detail") or f"http_{status}")
            print(f"Login failed: {error}")
            self.password = ""
        return False

    def _menu_loop(self) -> int:
        while True:
            print("\n=== Admin Menu ===")
            print("1) List teachers")
            print("2) Disable teacher")
            print("3) Enable teacher")
            print("4) Reset teacher password (auto-generate)")
            print("5) Reset teacher password (manual input)")
            print("q) Quit")
            choice = input("Select: ").strip().lower()

            if choice == "1":
                self._list_teachers()
            elif choice == "2":
                self._set_teacher_disabled(True)
            elif choice == "3":
                self._set_teacher_disabled(False)
            elif choice == "4":
                self._reset_teacher_password(auto_generate=True)
            elif choice == "5":
                self._reset_teacher_password(auto_generate=False)
            elif choice in {"q", "quit", "exit"}:
                print("Bye.")
                return 0
            else:
                print("Unknown option.")

    def _list_teachers(self) -> None:
        if self.trusted_local:
            payload = self._local_store.list_teacher_auth_status()
            if payload.get("ok") is not True:
                print(f"Request failed: {payload.get('error')}")
                return
        else:
            status, payload = _request_json(
                method="GET",
                url=f"{self.base_url}/auth/admin/teacher/list",
                bearer_token=self.access_token,
            )
            if status != 200 or payload.get("ok") is not True:
                error = str(payload.get("error") or payload.get("detail") or f"http_{status}")
                print(f"Request failed: {error}")
                return
        items = payload.get("items") or []
        if not isinstance(items, list):
            print("Unexpected response format.")
            return
        print(_format_teacher_rows([item for item in items if isinstance(item, dict)]))

    def _set_teacher_disabled(self, disabled: bool) -> None:
        target_id = _read_non_empty("Teacher ID: ")
        if self.trusted_local:
            payload = self._local_store.set_teacher_disabled(
                target_id=target_id,
                is_disabled=bool(disabled),
                actor_id=self.local_actor_id,
                actor_role="admin",
            )
            if payload.get("ok") is not True:
                print(f"Request failed: {payload.get('error')}")
                return
        else:
            status, payload = _request_json(
                method="POST",
                url=f"{self.base_url}/auth/admin/teacher/set-disabled",
                payload={"target_id": target_id, "is_disabled": bool(disabled)},
                bearer_token=self.access_token,
            )
            if status != 200 or payload.get("ok") is not True:
                error = str(payload.get("error") or payload.get("detail") or f"http_{status}")
                print(f"Request failed: {error}")
                return
        state_text = "disabled" if bool(payload.get("is_disabled")) else "enabled"
        tv = payload.get("token_version")
        print(f"Teacher {target_id} is now {state_text}. token_version={tv}")

    def _reset_teacher_password(self, *, auto_generate: bool) -> None:
        target_id = _read_non_empty("Teacher ID: ")
        new_password: Optional[str]
        if auto_generate:
            new_password = None
        else:
            first = getpass.getpass("New password: ")
            second = getpass.getpass("Confirm password: ")
            if first != second:
                print("Password mismatch.")
                return
            new_password = first

        if self.trusted_local:
            payload = self._local_store.reset_teacher_password(
                target_id=target_id,
                new_password=new_password,
                actor_id=self.local_actor_id,
                actor_role="admin",
            )
            if payload.get("ok") is not True:
                print(f"Request failed: {payload.get('error')}")
                return
        else:
            body: Dict[str, Any] = {"target_id": target_id}
            if new_password is not None:
                body["new_password"] = new_password
            status, payload = _request_json(
                method="POST",
                url=f"{self.base_url}/auth/admin/teacher/reset-password",
                payload=body,
                bearer_token=self.access_token,
            )
            if status != 200 or payload.get("ok") is not True:
                error = str(payload.get("error") or payload.get("detail") or f"http_{status}")
                print(f"Request failed: {error}")
                return

        print(f"Teacher {target_id} password reset done. token_version={payload.get('token_version')}")
        if bool(payload.get("generated_password")):
            print(f"Temporary password: {payload.get('temp_password')}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Admin TUI for teacher account management")
    parser.add_argument(
        "--base-url",
        default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"),
        help="API base URL (default: %(default)s)",
    )
    parser.add_argument("--username", default="", help="Admin username (optional)")
    parser.add_argument("--password", default="", help="Admin password (optional)")
    parser.add_argument(
        "--trusted-local",
        action="store_true",
        default=_truthy(os.getenv("ADMIN_MANAGER_TRUSTED_LOCAL", "0")),
        help="Skip admin login and use local trusted mode",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    app = AdminAuthTUI(
        base_url=str(args.base_url or ""),
        username=str(args.username or "").strip() or None,
        password=str(args.password or "") or None,
        trusted_local=bool(args.trusted_local),
    )
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
