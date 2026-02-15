from __future__ import annotations

import argparse
import getpass
import json
import os
import shlex
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from math import ceil
from typing import Any, Dict, List, Optional, Set, Tuple

MAX_HISTORY = 50
BULK_CONFIRM_THRESHOLD = 5


@dataclass
class ViewState:
    filter_query: str = ""
    filter_disabled: Optional[bool] = None
    filter_password_set: Optional[bool] = None
    sort_field: str = "teacher_id"
    sort_desc: bool = False
    page_size: int = 20
    page: int = 1
    selected_ids: Set[str] = field(default_factory=set)
    history: List[Dict[str, Any]] = field(default_factory=list)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _normalize_base_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "http://127.0.0.1:8000"
    return text.rstrip("/")


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _parse_bool_or_any(raw: str) -> Optional[bool]:
    text = _normalize_text(raw)
    if text in {"any", "*", "", "all"}:
        return None
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError("expected one of: true/false/any")


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


def _as_bool(value: Any) -> bool:
    return bool(value)


def _teacher_sort_key(item: Dict[str, Any], field_name: str) -> Tuple[Any, ...]:
    if field_name == "is_disabled":
        return (1 if _as_bool(item.get("is_disabled")) else 0, _normalize_text(item.get("teacher_id")))
    if field_name == "password_set":
        return (1 if _as_bool(item.get("password_set")) else 0, _normalize_text(item.get("teacher_id")))
    if field_name == "token_version":
        return (int(item.get("token_version") or 0), _normalize_text(item.get("teacher_id")))
    return (_normalize_text(item.get(field_name)), _normalize_text(item.get("teacher_id")))


def _apply_filters(items: List[Dict[str, Any]], state: ViewState) -> List[Dict[str, Any]]:
    query = _normalize_text(state.filter_query)
    filtered: List[Dict[str, Any]] = []
    for item in items:
        if state.filter_disabled is not None and _as_bool(item.get("is_disabled")) != state.filter_disabled:
            continue
        if state.filter_password_set is not None and _as_bool(item.get("password_set")) != state.filter_password_set:
            continue
        if query:
            search_blob = " ".join(
                [
                    str(item.get("teacher_id") or ""),
                    str(item.get("teacher_name") or ""),
                    str(item.get("email") or ""),
                ]
            ).lower()
            if query not in search_blob:
                continue
        filtered.append(item)
    filtered.sort(key=lambda row: _teacher_sort_key(row, state.sort_field), reverse=state.sort_desc)
    return filtered


def _clamp_page(total: int, page_size: int, page: int) -> int:
    if total <= 0:
        return 1
    pages = max(1, ceil(total / max(1, page_size)))
    return max(1, min(page, pages))


def _format_teacher_rows(
    *,
    items: List[Dict[str, Any]],
    selected_ids: Set[str],
    start_index: int,
) -> str:
    if not items:
        return "(no teachers in current view)"
    headers = ["#", "Sel", "Teacher ID", "Name", "Email", "Pwd", "Disabled", "TV"]
    rows: List[List[str]] = []
    widths = [len(col) for col in headers]

    for idx, item in enumerate(items, start=1):
        teacher_id = str(item.get("teacher_id") or "")
        row = [
            str(start_index + idx),
            "*" if teacher_id in selected_ids else "",
            teacher_id,
            str(item.get("teacher_name") or ""),
            str(item.get("email") or ""),
            "Y" if _as_bool(item.get("password_set")) else "N",
            "Y" if _as_bool(item.get("is_disabled")) else "N",
            str(item.get("token_version") or 0),
        ]
        rows.append(row)
        for c_idx, cell in enumerate(row):
            widths[c_idx] = max(widths[c_idx], len(cell))

    def _line(values: List[str]) -> str:
        return " | ".join(values[i].ljust(widths[i]) for i in range(len(values)))

    title = _line(headers)
    sep = "-+-".join("-" * widths[i] for i in range(len(widths)))
    body = "\n".join(_line(row) for row in rows)
    return f"{title}\n{sep}\n{body}"


def _parse_selection_expr(expr: str, page_items: List[Dict[str, Any]]) -> Set[str]:
    text = str(expr or "").strip()
    if not text:
        raise ValueError("missing selection expression")

    out: Set[str] = set()
    tokens = [part.strip() for part in text.split(",") if part.strip()]
    for token in tokens:
        if "-" in token and all(piece.strip().isdigit() for piece in token.split("-", 1)):
            left_s, right_s = token.split("-", 1)
            left = int(left_s)
            right = int(right_s)
            if left > right:
                left, right = right, left
            for pos in range(left, right + 1):
                if pos <= 0 or pos > len(page_items):
                    continue
                out.add(str(page_items[pos - 1].get("teacher_id") or ""))
            continue

        if token.isdigit():
            pos = int(token)
            if pos > 0 and pos <= len(page_items):
                out.add(str(page_items[pos - 1].get("teacher_id") or ""))
            continue

        token_norm = token
        if token.startswith("id:"):
            token_norm = token[3:].strip()
        if token_norm:
            out.add(token_norm)

    return {item for item in out if item}


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
        self.state = ViewState()
        self.teachers_all: List[Dict[str, Any]] = []

    def run(self) -> int:
        if self.trusted_local:
            if not self._init_local_mode():
                return 1
        else:
            print(f"Admin TUI endpoint: {self.base_url}")
            if not self._login_remote():
                return 1

        if not self._refresh_teachers(show_message=True):
            return 1
        return self._command_loop()

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

    def _record_history(
        self,
        *,
        action: str,
        total: int,
        success: int,
        failed: int,
        detail: str,
    ) -> None:
        event = {
            "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "action": action,
            "total": int(total),
            "success": int(success),
            "failed": int(failed),
            "detail": str(detail or ""),
        }
        self.state.history.append(event)
        if len(self.state.history) > MAX_HISTORY:
            self.state.history = self.state.history[-MAX_HISTORY:]

    def _fetch_teachers_payload(self) -> Dict[str, Any]:
        if self.trusted_local:
            return self._local_store.list_teacher_auth_status()
        status, payload = _request_json(
            method="GET",
            url=f"{self.base_url}/auth/admin/teacher/list",
            bearer_token=self.access_token,
        )
        if status != 200:
            return {"ok": False, "error": payload.get("error") or payload.get("detail") or f"http_{status}"}
        return payload

    def _refresh_teachers(self, *, show_message: bool = False) -> bool:
        payload = self._fetch_teachers_payload()
        if payload.get("ok") is not True:
            print(f"Refresh failed: {payload.get('error')}")
            return False
        items = payload.get("items") or []
        if not isinstance(items, list):
            print("Refresh failed: invalid response format")
            return False
        self.teachers_all = [item for item in items if isinstance(item, dict)]

        valid_ids = {str(item.get("teacher_id") or "") for item in self.teachers_all}
        self.state.selected_ids = {tid for tid in self.state.selected_ids if tid in valid_ids}

        filtered = self._filtered_items()
        self.state.page = _clamp_page(len(filtered), self.state.page_size, self.state.page)
        if show_message:
            print(f"Loaded {len(self.teachers_all)} teachers.")
        return True

    def _filtered_items(self) -> List[Dict[str, Any]]:
        return _apply_filters(self.teachers_all, self.state)

    def _paged_items(self) -> Tuple[List[Dict[str, Any]], int, int]:
        filtered = self._filtered_items()
        total = len(filtered)
        self.state.page = _clamp_page(total, self.state.page_size, self.state.page)
        start = (self.state.page - 1) * self.state.page_size
        end = start + self.state.page_size
        return filtered[start:end], start, total

    def _status_header(self, total_filtered: int) -> str:
        pages = max(1, ceil(total_filtered / max(1, self.state.page_size))) if total_filtered > 0 else 1
        mode = "trusted-local" if self.trusted_local else "api-login"
        disabled_filter = "any" if self.state.filter_disabled is None else ("true" if self.state.filter_disabled else "false")
        pwd_filter = "any" if self.state.filter_password_set is None else ("true" if self.state.filter_password_set else "false")
        query = self.state.filter_query or "(none)"
        return (
            f"Mode={mode} | Total={len(self.teachers_all)} | Filtered={total_filtered} | "
            f"Page={self.state.page}/{pages} size={self.state.page_size} | Selected={len(self.state.selected_ids)}\n"
            f"Filters: query={query} disabled={disabled_filter} pwd={pwd_filter} | "
            f"Sort={self.state.sort_field} {'desc' if self.state.sort_desc else 'asc'}"
        )

    def _render_view(self) -> None:
        page_items, start, total_filtered = self._paged_items()
        print("\n=== Admin Manager ===")
        print(self._status_header(total_filtered))
        print(_format_teacher_rows(items=page_items, selected_ids=self.state.selected_ids, start_index=start))
        print("Hint: h(help)  f(filter)  sort  page/size  sel  batch  refresh  r(history)  q(quit)")

    def _show_help(self) -> None:
        print(
            """
Commands:
  h | help                      Show help
  refresh | rf                  Refresh teacher list from source
  n | p                         Next / previous page
  page <num>                    Go to page number
  size <num>                    Set page size (1-200)

  f clear                       Clear all filters
  f q <text>                    Set fuzzy query on id/name/email
  f disabled <true|false|any>   Filter by disabled status
  f pwd <true|false|any>        Filter by password_set status

  sort <field> [asc|desc]       Fields: id,name,email,disabled,pwd,tv

  sel clear                     Clear selection
  sel all                       Select all rows in current page
  sel visible                   Select all rows in current filtered view
  sel add <expr>                Add selection by page row index or teacher id
  sel set <expr>                Replace selection
  sel rm <expr>                 Remove selection
                                expr examples: 1,3-5 or id:teacher_a,teacher_b

  batch disable                 Disable all selected teachers
  batch enable                  Enable all selected teachers
  batch reset auto              Reset password for selected (auto-generate)
  batch reset manual            Reset password for selected (same manual password)

  disable <teacher_id>          Disable a teacher
  enable <teacher_id>           Enable a teacher
  reset <teacher_id> auto       Reset password (auto)
  reset <teacher_id> manual     Reset password (manual)

Compatibility aliases:
  1(list) 2(disable prompt) 3(enable prompt) 4(reset auto prompt) 5(reset manual prompt)
""".strip()
        )

    def _show_history(self) -> None:
        if not self.state.history:
            print("No operation history in this session.")
            return
        print("Recent operations:")
        for item in self.state.history[-20:]:
            print(
                f"- {item.get('ts')} | {item.get('action')} | total={item.get('total')} "
                f"ok={item.get('success')} fail={item.get('failed')} | {item.get('detail')}"
            )

    def _command_loop(self) -> int:
        while True:
            self._render_view()
            raw = input("admin> ").strip()
            if not raw:
                continue
            if not self._dispatch_command(raw):
                print("Bye.")
                return 0

    def _dispatch_command(self, raw: str) -> bool:
        cmd = _normalize_text(raw)
        if cmd in {"q", "quit", "exit"}:
            return False
        if cmd in {"h", "help", "?"}:
            self._show_help()
            return True
        if cmd in {"r", "history"}:
            self._show_history()
            return True
        if cmd in {"refresh", "rf", "1", "list", "ls"}:
            self._refresh_teachers(show_message=True)
            return True
        if cmd == "n":
            self.state.page += 1
            return True
        if cmd == "p":
            self.state.page = max(1, self.state.page - 1)
            return True
        if cmd == "2":
            target_id = _read_non_empty("Teacher ID: ")
            self._single_set_disabled(target_id=target_id, disabled=True)
            return True
        if cmd == "3":
            target_id = _read_non_empty("Teacher ID: ")
            self._single_set_disabled(target_id=target_id, disabled=False)
            return True
        if cmd == "4":
            target_id = _read_non_empty("Teacher ID: ")
            self._single_reset_password(target_id=target_id, auto_generate=True)
            return True
        if cmd == "5":
            target_id = _read_non_empty("Teacher ID: ")
            self._single_reset_password(target_id=target_id, auto_generate=False)
            return True

        try:
            args = shlex.split(raw)
        except Exception as exc:
            print(f"Parse error: {exc}")
            return True
        if not args:
            return True

        head = _normalize_text(args[0])
        tail = args[1:]

        if head == "page" and tail:
            self._cmd_page(tail)
            return True
        if head == "size" and tail:
            self._cmd_size(tail)
            return True
        if head in {"f", "filter"}:
            self._cmd_filter(tail)
            return True
        if head == "sort":
            self._cmd_sort(tail)
            return True
        if head in {"sel", "select"}:
            self._cmd_select(tail)
            return True
        if head == "batch":
            self._cmd_batch(tail)
            return True
        if head == "disable" and tail:
            self._single_set_disabled(target_id=tail[0], disabled=True)
            return True
        if head == "enable" and tail:
            self._single_set_disabled(target_id=tail[0], disabled=False)
            return True
        if head == "reset" and tail:
            mode = _normalize_text(tail[1]) if len(tail) > 1 else "auto"
            if mode not in {"auto", "manual"}:
                print("reset mode must be auto/manual")
                return True
            self._single_reset_password(target_id=tail[0], auto_generate=(mode == "auto"))
            return True

        print("Unknown command. Type 'h' for help.")
        return True

    def _cmd_page(self, tail: List[str]) -> None:
        try:
            page = int(tail[0])
            self.state.page = max(1, page)
        except Exception:
            print("Invalid page number.")

    def _cmd_size(self, tail: List[str]) -> None:
        try:
            size = int(tail[0])
            self.state.page_size = max(1, min(200, size))
            self.state.page = 1
        except Exception:
            print("Invalid page size.")

    def _cmd_filter(self, tail: List[str]) -> None:
        if not tail:
            print("Usage: f clear | f q <text> | f disabled <true|false|any> | f pwd <true|false|any>")
            return

        key = _normalize_text(tail[0])
        if key == "clear":
            self.state.filter_query = ""
            self.state.filter_disabled = None
            self.state.filter_password_set = None
            self.state.page = 1
            return

        if key == "q":
            self.state.filter_query = " ".join(tail[1:]).strip()
            self.state.page = 1
            return

        if key in {"disabled", "disable"} and len(tail) >= 2:
            try:
                self.state.filter_disabled = _parse_bool_or_any(tail[1])
                self.state.page = 1
            except ValueError as exc:
                print(f"Invalid filter: {exc}")
            return

        if key in {"pwd", "password", "password_set"} and len(tail) >= 2:
            try:
                self.state.filter_password_set = _parse_bool_or_any(tail[1])
                self.state.page = 1
            except ValueError as exc:
                print(f"Invalid filter: {exc}")
            return

        self.state.filter_query = " ".join(tail).strip()
        self.state.page = 1

    def _cmd_sort(self, tail: List[str]) -> None:
        if not tail:
            print("Usage: sort <id|name|email|disabled|pwd|tv> [asc|desc]")
            return
        field_map = {
            "id": "teacher_id",
            "name": "teacher_name",
            "email": "email",
            "disabled": "is_disabled",
            "pwd": "password_set",
            "tv": "token_version",
        }
        field = field_map.get(_normalize_text(tail[0]))
        if not field:
            print("Invalid sort field.")
            return
        direction = _normalize_text(tail[1]) if len(tail) > 1 else "asc"
        if direction not in {"asc", "desc"}:
            print("Sort direction must be asc/desc")
            return
        self.state.sort_field = field
        self.state.sort_desc = direction == "desc"
        self.state.page = 1

    def _current_page_items(self) -> List[Dict[str, Any]]:
        page_items, _, _ = self._paged_items()
        return page_items

    def _cmd_select(self, tail: List[str]) -> None:
        if not tail:
            print("Usage: sel clear|all|visible|add <expr>|set <expr>|rm <expr>")
            return

        op = _normalize_text(tail[0])
        if op == "clear":
            self.state.selected_ids.clear()
            return

        if op == "all":
            page_items = self._current_page_items()
            self.state.selected_ids.update(str(item.get("teacher_id") or "") for item in page_items)
            return

        if op == "visible":
            items = self._filtered_items()
            self.state.selected_ids.update(str(item.get("teacher_id") or "") for item in items)
            return

        if op in {"add", "set", "rm", "remove"}:
            if len(tail) < 2:
                print("Selection expression is required.")
                return
            expr = " ".join(tail[1:]).strip()
            page_items = self._current_page_items()
            try:
                picked = _parse_selection_expr(expr, page_items)
            except ValueError as exc:
                print(f"Selection error: {exc}")
                return
            if op == "add":
                self.state.selected_ids.update(picked)
            elif op == "set":
                self.state.selected_ids = set(picked)
            else:
                self.state.selected_ids = {tid for tid in self.state.selected_ids if tid not in picked}
            return

        print("Unknown sel command.")

    def _confirm_bulk(self, *, action: str, count: int) -> bool:
        if count <= BULK_CONFIRM_THRESHOLD:
            return True
        marker = f"{action.upper()} {count}"
        typed = input(f"Bulk action affects {count} users. Type '{marker}' to confirm: ").strip()
        return typed == marker

    def _selected_targets(self) -> List[str]:
        known = {str(item.get("teacher_id") or "") for item in self.teachers_all}
        return sorted(tid for tid in self.state.selected_ids if tid in known)

    def _cmd_batch(self, tail: List[str]) -> None:
        if not tail:
            print("Usage: batch disable|enable|reset auto|reset manual")
            return

        action = _normalize_text(tail[0])
        targets = self._selected_targets()
        if not targets:
            print("No selected teachers. Use 'sel ...' first.")
            return

        if action in {"disable", "enable"}:
            desired = action == "disable"
            marker = "disable" if desired else "enable"
            if not self._confirm_bulk(action=marker, count=len(targets)):
                print("Cancelled.")
                return
            self._batch_set_disabled(targets=targets, disabled=desired)
            return

        if action == "reset":
            mode = _normalize_text(tail[1]) if len(tail) > 1 else "auto"
            if mode not in {"auto", "manual"}:
                print("Usage: batch reset auto|manual")
                return
            if not self._confirm_bulk(action="reset", count=len(targets)):
                print("Cancelled.")
                return
            self._batch_reset_password(targets=targets, auto_generate=(mode == "auto"))
            return

        print("Unknown batch command.")

    def _api_set_teacher_disabled(self, *, target_id: str, is_disabled: bool) -> Dict[str, Any]:
        if self.trusted_local:
            return self._local_store.set_teacher_disabled(
                target_id=target_id,
                is_disabled=is_disabled,
                actor_id=self.local_actor_id,
                actor_role="admin",
            )
        status, payload = _request_json(
            method="POST",
            url=f"{self.base_url}/auth/admin/teacher/set-disabled",
            payload={"target_id": target_id, "is_disabled": is_disabled},
            bearer_token=self.access_token,
        )
        if status != 200:
            return {"ok": False, "error": payload.get("error") or payload.get("detail") or f"http_{status}"}
        return payload

    def _api_reset_teacher_password(self, *, target_id: str, new_password: Optional[str]) -> Dict[str, Any]:
        if self.trusted_local:
            return self._local_store.reset_teacher_password(
                target_id=target_id,
                new_password=new_password,
                actor_id=self.local_actor_id,
                actor_role="admin",
            )
        body: Dict[str, Any] = {"target_id": target_id}
        if new_password is not None:
            body["new_password"] = new_password
        status, payload = _request_json(
            method="POST",
            url=f"{self.base_url}/auth/admin/teacher/reset-password",
            payload=body,
            bearer_token=self.access_token,
        )
        if status != 200:
            return {"ok": False, "error": payload.get("error") or payload.get("detail") or f"http_{status}"}
        return payload

    def _single_set_disabled(self, *, target_id: str, disabled: bool) -> None:
        result = self._api_set_teacher_disabled(target_id=target_id, is_disabled=disabled)
        if result.get("ok") is not True:
            print(f"Request failed: {result.get('error')}")
            self._record_history(
                action="disable" if disabled else "enable",
                total=1,
                success=0,
                failed=1,
                detail=f"target={target_id}",
            )
            return
        state_text = "disabled" if bool(result.get("is_disabled")) else "enabled"
        print(f"Teacher {target_id} is now {state_text}. token_version={result.get('token_version')}")
        self._record_history(
            action="disable" if disabled else "enable",
            total=1,
            success=1,
            failed=0,
            detail=f"target={target_id}",
        )
        self._refresh_teachers(show_message=False)

    def _single_reset_password(self, *, target_id: str, auto_generate: bool) -> None:
        new_password: Optional[str] = None
        if not auto_generate:
            first = getpass.getpass("New password: ")
            second = getpass.getpass("Confirm password: ")
            if first != second:
                print("Password mismatch.")
                return
            new_password = first

        result = self._api_reset_teacher_password(target_id=target_id, new_password=new_password)
        if result.get("ok") is not True:
            print(f"Request failed: {result.get('error')}")
            self._record_history(
                action="reset_password",
                total=1,
                success=0,
                failed=1,
                detail=f"target={target_id}",
            )
            return

        print(f"Teacher {target_id} password reset done. token_version={result.get('token_version')}")
        if bool(result.get("generated_password")):
            print(f"Temporary password: {result.get('temp_password')}")
        self._record_history(
            action="reset_password",
            total=1,
            success=1,
            failed=0,
            detail=f"target={target_id}",
        )
        self._refresh_teachers(show_message=False)

    def _batch_set_disabled(self, *, targets: List[str], disabled: bool) -> None:
        success = 0
        failed = 0
        errors: List[str] = []
        for target_id in targets:
            result = self._api_set_teacher_disabled(target_id=target_id, is_disabled=disabled)
            if result.get("ok") is True:
                success += 1
            else:
                failed += 1
                errors.append(f"{target_id}:{result.get('error')}")

        print(
            f"Batch {'disable' if disabled else 'enable'} done. total={len(targets)} "
            f"ok={success} fail={failed}"
        )
        if errors:
            print("Failures:")
            for item in errors[:20]:
                print(f"- {item}")
        self._record_history(
            action="batch_disable" if disabled else "batch_enable",
            total=len(targets),
            success=success,
            failed=failed,
            detail=",".join(targets[:5]) + ("..." if len(targets) > 5 else ""),
        )
        self._refresh_teachers(show_message=False)

    def _batch_reset_password(self, *, targets: List[str], auto_generate: bool) -> None:
        shared_password: Optional[str] = None
        if not auto_generate:
            first = getpass.getpass("New shared password: ")
            second = getpass.getpass("Confirm shared password: ")
            if first != second:
                print("Password mismatch.")
                return
            shared_password = first

        success = 0
        failed = 0
        temp_pw_rows: List[Tuple[str, str]] = []
        errors: List[str] = []

        for target_id in targets:
            result = self._api_reset_teacher_password(target_id=target_id, new_password=shared_password)
            if result.get("ok") is True:
                success += 1
                if bool(result.get("generated_password")):
                    temp_pw_rows.append((target_id, str(result.get("temp_password") or "")))
            else:
                failed += 1
                errors.append(f"{target_id}:{result.get('error')}")

        print(f"Batch reset done. total={len(targets)} ok={success} fail={failed}")
        if temp_pw_rows:
            print("Temporary passwords:")
            width = max(len("Teacher ID"), *(len(row[0]) for row in temp_pw_rows))
            print(f"{'Teacher ID'.ljust(width)} | Password")
            print(f"{'-' * width}-+-{'-' * 24}")
            for teacher_id, temp_password in temp_pw_rows:
                print(f"{teacher_id.ljust(width)} | {temp_password}")

        if errors:
            print("Failures:")
            for item in errors[:20]:
                print(f"- {item}")

        self._record_history(
            action="batch_reset_password",
            total=len(targets),
            success=success,
            failed=failed,
            detail="auto" if auto_generate else "manual-shared",
        )
        self._refresh_teachers(show_message=False)


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
