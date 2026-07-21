"""Unit tests for WordPress JWT user-id / roles resolution helpers."""

from __future__ import annotations

from api.auth_wp import (
    WpAuthResult,
    _extract_token,
    _parse_validate_body,
    _user_id_from_validate_body,
)


def test_extract_token_simple_jwt():
    assert (
        _extract_token({"success": True, "data": {"jwt": "abc.def.ghi"}})
        == "abc.def.ghi"
    )


def test_extract_token_tmeister():
    assert _extract_token({"token": "tmeister-token"}) == "tmeister-token"


def test_user_id_from_validate_body():
    body = {
        "success": True,
        "data": {
            "user": {"ID": "42", "user_email": "a@b.c"},
            "jwt": [{"payload": {"id": 42}}],
        },
    }
    assert _user_id_from_validate_body(body) == 42


def test_user_id_from_validate_payload_fallback():
    body = {
        "success": True,
        "data": {
            "user": {},
            "jwt": [{"payload": {"id": 7}}],
        },
    }
    assert _user_id_from_validate_body(body) == 7


def test_user_id_from_validate_rejects_failure():
    assert _user_id_from_validate_body({"success": False, "data": {"user": {"ID": 1}}}) is None


def test_parse_validate_body_includes_roles():
    body = {
        "success": True,
        "data": {
            "user": {"ID": "9"},
            "roles": ["administrator", "subscriber"],
        },
    }
    parsed = _parse_validate_body(body)
    assert parsed == (9, ["administrator", "subscriber"])


def test_wp_auth_result_is_admin():
    assert WpAuthResult(user_id=1, roles=["administrator"]).is_admin is True
    assert WpAuthResult(user_id=1, roles=["editor"]).is_admin is False
    assert WpAuthResult(user_id=1, roles=[]).is_admin is False
