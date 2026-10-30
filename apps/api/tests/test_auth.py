"""Only requests the web app signed for a real user get through."""

from __future__ import annotations

import pytest

from app.auth import check_secret
from app.config import Settings
from tests.conftest import auth


def test_health_needs_no_sign_in(client):
    assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Basic abc"},
        {"Authorization": "Bearer not-a-token"},
    ],
)
def test_no_valid_token_is_a_401(client, user, headers):
    assert client.get("/me", headers=headers).status_code == 401


def test_a_token_signed_with_another_secret_is_refused(client, user):
    assert client.get("/me", headers=auth(user.id, secret="another-secret-" + "y" * 40)).status_code == 401


def test_an_expired_token_is_refused(client, user):
    assert client.get("/me", headers=auth(user.id, minutes=-1)).status_code == 401


def test_a_token_meant_for_something_else_is_refused(client, user):
    assert client.get("/me", headers=auth(user.id, aud="some-other-api")).status_code == 401
    assert client.get("/me", headers=auth(user.id, iss="someone-else")).status_code == 401


def test_a_token_for_a_user_that_does_not_exist_is_refused(client, user):
    assert client.get("/me", headers=auth(user.id + 1000)).status_code == 401


def test_the_api_will_not_start_without_a_long_enough_secret():
    with pytest.raises(RuntimeError, match="BACKEND_JWT_SECRET"):
        check_secret(Settings(backend_jwt_secret="short"))
    check_secret(Settings(backend_jwt_secret="z" * 32))
