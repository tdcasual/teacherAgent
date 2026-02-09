"""LLM routing proposals — CRUD for routing change proposals.

Extracted from llm_routing.py. Depends on llm_routing for config
application and validation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = [
    "create_routing_proposal",
    "read_proposal",
    "list_proposals",
    "apply_routing_proposal",
]


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def create_routing_proposal(
    config_path: Path,
    model_registry: Dict[str, Any],
    config_payload: Dict[str, Any],
    actor: str,
    note: str = "",
) -> Dict[str, Any]:
    from . import llm_routing as _lr
    validation = _lr.validate_routing_config(config_payload, model_registry)
    proposal_id = _lr._safe_id("proposal")
    proposal = {
        "proposal_id": proposal_id,
        "created_at": _lr._now_iso(),
        "created_by": actor or "unknown",
        "status": "pending",
        "note": note or "",
        "candidate": validation.get("normalized") if validation.get("ok") else (config_payload or {}),
        "validation": {
            "ok": bool(validation.get("ok")),
            "errors": validation.get("errors") or [],
            "warnings": validation.get("warnings") or [],
        },
    }
    proposals_dir = _proposals_dir(config_path)
    proposals_dir.mkdir(parents=True, exist_ok=True)
    path = proposals_dir / f"{proposal_id}.json"
    _lr._atomic_write_json(path, proposal)
    return {
        "ok": True,
        "proposal_id": proposal_id,
        "status": "pending",
        "validation": proposal["validation"],
        "proposal_path": str(path),
    }


def _proposals_dir(config_path: Path) -> Path:
    return config_path.parent / "llm_routing_proposals"


def _proposal_path(config_path: Path, proposal_id: str) -> Path:
    return _proposals_dir(config_path) / f"{proposal_id}.json"


def read_proposal(config_path: Path, proposal_id: str) -> Dict[str, Any]:
    from . import llm_routing as _lr
    path = _proposal_path(config_path, _as_str(proposal_id))
    data = _lr._read_json(path)
    if not data:
        return {"ok": False, "error": "proposal_not_found", "proposal_id": proposal_id}
    return {"ok": True, "proposal": data, "proposal_path": str(path)}


def list_proposals(config_path: Path, limit: int = 20, status: Optional[str] = None) -> List[Dict[str, Any]]:
    from . import llm_routing as _lr
    base = _proposals_dir(config_path)
    if not base.exists():
        return []
    items: List[Dict[str, Any]] = []
    for path in base.glob("*.json"):
        data = _lr._read_json(path)
        row = {
            "proposal_id": _as_str(data.get("proposal_id")) or path.stem,
            "created_at": _as_str(data.get("created_at")),
            "created_by": _as_str(data.get("created_by")),
            "status": _as_str(data.get("status")) or "pending",
            "note": _as_str(data.get("note")),
            "validation_ok": bool(((data.get("validation") or {}).get("ok"))),
            "proposal_path": str(path),
        }
        if status and row["status"] != status:
            continue
        items.append(row)
    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    take = max(1, min(int(limit), 200))
    return items[:take]


def apply_routing_proposal(
    config_path: Path,
    model_registry: Dict[str, Any],
    proposal_id: str,
    approve: bool,
    actor: str,
) -> Dict[str, Any]:
    from . import llm_routing as _lr
    proposal_id = _as_str(proposal_id)
    if not proposal_id:
        return {"ok": False, "error": "proposal_id_required"}
    lock = _lr._config_lock(config_path)
    with lock:
        path = _proposal_path(config_path, proposal_id)
        proposal = _lr._read_json(path)
        if not proposal:
            return {"ok": False, "error": "proposal_not_found", "proposal_id": proposal_id}
        if _as_str(proposal.get("status")) in {"applied", "rejected"}:
            return {"ok": False, "error": "proposal_already_reviewed", "proposal_id": proposal_id}

        proposal["reviewed_at"] = _lr._now_iso()
        proposal["reviewed_by"] = actor or "unknown"
        if not approve:
            proposal["status"] = "rejected"
            _lr._atomic_write_json(path, proposal)
            return {"ok": True, "proposal_id": proposal_id, "status": "rejected"}

        candidate = proposal.get("candidate") if isinstance(proposal.get("candidate"), dict) else {}
        apply_res = _lr.apply_routing_config(
            config_path=config_path,
            model_registry=model_registry,
            config_payload=candidate,
            actor=actor,
            source=f"proposal:{proposal_id}",
            note=_as_str(proposal.get("note")),
        )
        if not apply_res.get("ok"):
            proposal["status"] = "failed"
            proposal["apply_error"] = apply_res
            _lr._atomic_write_json(path, proposal)
            return {"ok": False, "proposal_id": proposal_id, "status": "failed", "error": apply_res}

        proposal["status"] = "applied"
        proposal["applied_version"] = apply_res.get("version")
        proposal["history_path"] = apply_res.get("history_path")
        _lr._atomic_write_json(path, proposal)
        return {
            "ok": True,
            "proposal_id": proposal_id,
            "status": "applied",
            "version": apply_res.get("version"),
            "history_path": apply_res.get("history_path"),
        }