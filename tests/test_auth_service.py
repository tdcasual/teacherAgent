"""Tests for services.api.auth_service."""
from __future__ import annotations

import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.api.auth_service import (
    AuthError,
    AuthPrincipal,
    _decode_bearer_token,
    auth_required,
    bind_chat_request_to_principal,
    enforce_chat_job_access,
    mint_test_token,
    principal_can_access_tenant,
    require_principal,
    resolve_principal_from_headers,
    resolve_student_scope,
    resolve_teacher_scope,
    set_current_principal,
)

SECRET = "test-secret-key-for-unit-tests"

# Force auth on for most tests
_AUTH_ON = {"AUTH_REQUIRED": "1", "AUTH_TOKEN_SECRET": SECRET}
_AUTH_OFF = {"AUTH_REQUIRED": "0"}


def _set_principal(role="teacher", actor_id="T001", tenant_id="tenant-1"):
    """Helper: set a principal in context and return (principal, token)."""
    p = AuthPrincipal(actor_id=actor_id, role=role, tenant_id=tenant_id)
    tok = set_current_principal(p)
    return p, tok


class TestMintAndDecode(unittest.TestCase):
    """Token minting and decoding roundtrip."""

    def test_roundtrip(self):
        claims = {"sub": "T001", "role": "teacher", "tenant_id": "t1"}
        token = mint_test_token(claims, secret=SECRET)
        p = _decode_bearer_token(token, secret=SECRET)
        self.assertEqual(p.actor_id, "T001")
        self.assertEqual(p.role, "teacher")
        self.assertEqual(p.tenant_id, "t1")

    def test_actor_id_from_actor_id_field(self):
        claims = {"actor_id": "A99", "role": "admin"}
        token = mint_test_token(claims, secret=SECRET)
        p = _decode_bearer_token(token, secret=SECRET)
        self.assertEqual(p.actor_id, "A99")

    def test_exp_preserved(self):
        future = int(time.time()) + 3600
        claims = {"sub": "T1", "role": "teacher", "exp": future}
        token = mint_test_token(claims, secret=SECRET)
        p = _decode_bearer_token(token, secret=SECRET)
        self.assertEqual(p.exp, future)

    def test_expired_token_rejected(self):
        claims = {"sub": "T1", "role": "teacher", "exp": int(time.time()) - 60}
        token = mint_test_token(claims, secret=SECRET)
        with self.assertRaises(AuthError) as ctx:
            _decode_bearer_token(token, secret=SECRET)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("expired", ctx.exception.detail)

    def test_invalid_signature(self):
        claims = {"sub": "T1", "role": "teacher"}
        token = mint_test_token(claims, secret=SECRET)
        with self.assertRaises(AuthError) as ctx:
            _decode_bearer_token(token, secret="wrong-secret")
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("signature", ctx.exception.detail)

    def test_malformed_token_wrong_segments(self):
        with self.assertRaises(AuthError) as ctx:
            _decode_bearer_token("a.b.c", secret=SECRET)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("format", ctx.exception.detail)

    def test_empty_token(self):
        with self.assertRaises(AuthError) as ctx:
            _decode_bearer_token("", secret=SECRET)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("missing", ctx.exception.detail)

    def test_none_token(self):
        with self.assertRaises(AuthError) as ctx:
            _decode_bearer_token(None, secret=SECRET)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_invalid_role_rejected(self):
        claims = {"sub": "X1", "role": "hacker"}
        token = mint_test_token(claims, secret=SECRET)
        with self.assertRaises(AuthError) as ctx:
            _decode_bearer_token(token, secret=SECRET)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("claims", ctx.exception.detail)

    def test_missing_sub_rejected(self):
        claims = {"role": "teacher"}
        token = mint_test_token(claims, secret=SECRET)
        with self.assertRaises(AuthError) as ctx:
            _decode_bearer_token(token, secret=SECRET)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("claims", ctx.exception.detail)


class TestAuthRequired(unittest.TestCase):
    """auth_required() reads AUTH_REQUIRED env var."""

    @patch.dict(os.environ, {"AUTH_REQUIRED": "1"}, clear=False)
    def test_enabled(self):
        self.assertTrue(auth_required())

    @patch.dict(os.environ, {"AUTH_REQUIRED": "0"}, clear=False)
    def test_disabled(self):
        self.assertFalse(auth_required())

    def test_unset_in_pytest(self):
        env = os.environ.copy()
        env.pop("AUTH_REQUIRED", None)
        env["PYTEST_CURRENT_TEST"] = "yes"
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(auth_required())


class TestResolvePrincipalFromHeaders(unittest.TestCase):
    """resolve_principal_from_headers with various header/path combos."""

    def _bearer(self, role="teacher", actor_id="T001"):
        claims = {"sub": actor_id, "role": role, "exp": int(time.time()) + 3600}
        token = mint_test_token(claims, secret=SECRET)
        return {"authorization": f"Bearer {token}"}

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_exempt_health_path(self):
        result = resolve_principal_from_headers({}, path="/health", method="GET")
        self.assertIsNone(result)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_exempt_admin_path(self):
        result = resolve_principal_from_headers({}, path="/admin/stats", method="GET")
        self.assertIsNone(result)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_exempt_admin_login_path(self):
        result = resolve_principal_from_headers({}, path="/auth/admin/login", method="POST")
        self.assertIsNone(result)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_options_method_bypass(self):
        result = resolve_principal_from_headers({}, path="/api/data", method="OPTIONS")
        self.assertIsNone(result)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_valid_bearer(self):
        p = resolve_principal_from_headers(self._bearer(), path="/api/data", method="GET")
        self.assertIsNotNone(p)
        self.assertEqual(p.actor_id, "T001")
        self.assertEqual(p.role, "teacher")

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_missing_authorization(self):
        with self.assertRaises(AuthError) as ctx:
            resolve_principal_from_headers({}, path="/api/data", method="GET")
        self.assertEqual(ctx.exception.status_code, 401)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_non_bearer_scheme(self):
        with self.assertRaises(AuthError) as ctx:
            resolve_principal_from_headers(
                {"authorization": "Basic abc123"}, path="/api/data", method="GET"
            )
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("scheme", ctx.exception.detail)


class TestRequirePrincipal(unittest.TestCase):
    """require_principal with role enforcement."""

    def tearDown(self):
        set_current_principal(None)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_no_principal_raises_401(self):
        set_current_principal(None)
        with self.assertRaises(AuthError) as ctx:
            require_principal()
        self.assertEqual(ctx.exception.status_code, 401)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_wrong_role_raises_403(self):
        _set_principal(role="student", actor_id="S001")
        with self.assertRaises(AuthError) as ctx:
            require_principal(roles=["teacher", "admin"])
        self.assertEqual(ctx.exception.status_code, 403)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_correct_role_passes(self):
        _set_principal(role="teacher", actor_id="T001")
        p = require_principal(roles=["teacher", "admin"])
        self.assertEqual(p.actor_id, "T001")


class TestPrincipalCanAccessTenant(unittest.TestCase):
    """Tenant access checks."""

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_admin_always_true(self):
        p = AuthPrincipal(actor_id="A1", role="admin", tenant_id="")
        self.assertTrue(principal_can_access_tenant(p, "any-tenant"))

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_matching_tenant(self):
        p = AuthPrincipal(actor_id="T1", role="teacher", tenant_id="t-100")
        self.assertTrue(principal_can_access_tenant(p, "t-100"))

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_non_matching_tenant(self):
        p = AuthPrincipal(actor_id="T1", role="teacher", tenant_id="t-100")
        self.assertFalse(principal_can_access_tenant(p, "t-999"))

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_none_principal(self):
        self.assertFalse(principal_can_access_tenant(None, "t-100"))

    @patch.dict(os.environ, _AUTH_OFF, clear=False)
    def test_auth_off_always_true(self):
        self.assertTrue(principal_can_access_tenant(None, "t-100"))


class TestResolveTeacherScope(unittest.TestCase):
    """Teacher scope enforcement."""

    def tearDown(self):
        set_current_principal(None)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_teacher_own_id(self):
        _set_principal(role="teacher", actor_id="T001")
        result = resolve_teacher_scope("T001")
        self.assertEqual(result, "T001")

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_teacher_other_id_forbidden(self):
        _set_principal(role="teacher", actor_id="T001")
        with self.assertRaises(AuthError) as ctx:
            resolve_teacher_scope("T999")
        self.assertEqual(ctx.exception.status_code, 403)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_teacher_none_returns_own(self):
        _set_principal(role="teacher", actor_id="T001")
        result = resolve_teacher_scope(None)
        self.assertEqual(result, "T001")

    @patch.dict(os.environ, _AUTH_OFF, clear=False)
    def test_auth_off_passthrough(self):
        result = resolve_teacher_scope("T999")
        self.assertEqual(result, "T999")


class TestResolveStudentScope(unittest.TestCase):
    """Student scope enforcement."""

    def tearDown(self):
        set_current_principal(None)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_student_own_id(self):
        _set_principal(role="student", actor_id="S001")
        result = resolve_student_scope("S001")
        self.assertEqual(result, "S001")

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_student_other_id_forbidden(self):
        _set_principal(role="student", actor_id="S001")
        with self.assertRaises(AuthError) as ctx:
            resolve_student_scope("S999")
        self.assertEqual(ctx.exception.status_code, 403)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_student_none_returns_own(self):
        _set_principal(role="student", actor_id="S001")
        result = resolve_student_scope(None)
        self.assertEqual(result, "S001")


class TestEnforceChatJobAccess(unittest.TestCase):
    """Chat job ownership checks."""

    def tearDown(self):
        set_current_principal(None)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_teacher_owns_job(self):
        _set_principal(role="teacher", actor_id="T001")
        job = {"teacher_id": "T001", "role": "teacher"}
        enforce_chat_job_access(job)  # should not raise

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_teacher_mismatch(self):
        _set_principal(role="teacher", actor_id="T001")
        job = {"teacher_id": "T999", "role": "teacher"}
        with self.assertRaises(AuthError) as ctx:
            enforce_chat_job_access(job)
        self.assertEqual(ctx.exception.status_code, 403)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_student_owns_job(self):
        _set_principal(role="student", actor_id="S001")
        job = {"student_id": "S001", "role": "student"}
        enforce_chat_job_access(job)  # should not raise

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_student_mismatch(self):
        _set_principal(role="student", actor_id="S001")
        job = {"student_id": "S999", "role": "student"}
        with self.assertRaises(AuthError) as ctx:
            enforce_chat_job_access(job)
        self.assertEqual(ctx.exception.status_code, 403)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_admin_bypasses(self):
        _set_principal(role="admin", actor_id="A001")
        job = {"teacher_id": "T999", "role": "teacher"}
        enforce_chat_job_access(job)  # should not raise

    @patch.dict(os.environ, _AUTH_OFF, clear=False)
    def test_auth_off_skips(self):
        set_current_principal(None)
        enforce_chat_job_access({"teacher_id": "T999"})  # should not raise


class TestBindChatRequestToPrincipal(unittest.TestCase):
    """bind_chat_request_to_principal for teacher, student, admin."""

    def tearDown(self):
        set_current_principal(None)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_teacher_binding(self):
        _set_principal(role="teacher", actor_id="T001")
        req = SimpleNamespace(role="", teacher_id="", student_id="")
        result = bind_chat_request_to_principal(req)
        self.assertEqual(result.role, "teacher")
        self.assertEqual(result.teacher_id, "T001")
        self.assertIsNone(result.student_id)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_student_binding(self):
        _set_principal(role="student", actor_id="S001")
        req = SimpleNamespace(role="", teacher_id="", student_id="")
        result = bind_chat_request_to_principal(req)
        self.assertEqual(result.role, "student")
        self.assertEqual(result.student_id, "S001")
        self.assertIsNone(result.teacher_id)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_admin_teacher_role(self):
        _set_principal(role="admin", actor_id="A001")
        req = SimpleNamespace(role="teacher", teacher_id="T050", student_id="")
        result = bind_chat_request_to_principal(req)
        self.assertEqual(result.teacher_id, "T050")
        self.assertIsNone(result.student_id)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_admin_student_role(self):
        _set_principal(role="admin", actor_id="A001")
        req = SimpleNamespace(role="student", teacher_id="", student_id="S050")
        result = bind_chat_request_to_principal(req)
        self.assertEqual(result.student_id, "S050")
        self.assertIsNone(result.teacher_id)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_admin_missing_role_raises(self):
        _set_principal(role="admin", actor_id="A001")
        req = SimpleNamespace(role="", teacher_id="", student_id="")
        with self.assertRaises(AuthError) as ctx:
            bind_chat_request_to_principal(req)
        self.assertEqual(ctx.exception.status_code, 400)

    @patch.dict(os.environ, _AUTH_ON, clear=False)
    def test_admin_teacher_missing_id_raises(self):
        _set_principal(role="admin", actor_id="A001")
        req = SimpleNamespace(role="teacher", teacher_id="", student_id="")
        with self.assertRaises(AuthError) as ctx:
            bind_chat_request_to_principal(req)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("teacher_id", ctx.exception.detail)
