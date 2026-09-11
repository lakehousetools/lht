"""
Unit tests for lht.user.salesforce_auth.login_user_flow().

requests.post is replaced with a fake, so nothing here reaches Salesforce and no
real credential is needed. The fake records exactly what would have been sent,
which is what these tests are about: where the client secret travels.
"""
import pytest
import requests

from lht.user import salesforce_auth

SECRET = "not-a-real-secret-0123456789ABCDEF"
CLIENT_ID = "3MVG9-not-a-real-client-id"


class _FakeResponse:
    def __init__(self, status_code, url, payload=None):
        self.status_code = status_code
        self.url = url
        self._payload = payload or {}
        self.reason = "Bad Request" if status_code >= 400 else "OK"

    def json(self):
        return self._payload

    def raise_for_status(self):
        # Mirrors requests' real message format, which is what made the old
        # query-string version leak: it embeds the full request URL.
        if self.status_code >= 400:
            raise requests.HTTPError(
                f"{self.status_code} Client Error: {self.reason} for url: {self.url}")


@pytest.fixture
def captured(monkeypatch):
    """Replace requests.post and keep the last call's arguments."""
    calls = {}

    def fake_post(url, data=None, headers=None, timeout=None, **kwargs):
        calls.update(url=url, data=data, headers=headers, timeout=timeout, kwargs=kwargs)
        return _FakeResponse(calls.get("status", 200), url,
                             {"access_token": "tok", "instance_url": "https://x"})

    monkeypatch.setattr(salesforce_auth.requests, "post", fake_post)
    return calls


def test_secret_is_not_in_the_url(captured):
    salesforce_auth.login_user_flow(CLIENT_ID, SECRET, "example--sandbox.sandbox")
    assert SECRET not in captured["url"]
    assert "?" not in captured["url"], "token URL should carry no query string at all"


def test_credentials_travel_as_a_form_body(captured):
    salesforce_auth.login_user_flow(CLIENT_ID, SECRET, "example--sandbox.sandbox")
    assert captured["data"] == {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": SECRET,
    }
    # data= makes requests send application/x-www-form-urlencoded, which the token
    # endpoint expects. An explicit application/json Content-Type would override that.
    assert "Content-Type" not in (captured["headers"] or {})


def test_url_targets_the_my_domain_token_endpoint(captured):
    salesforce_auth.login_user_flow(CLIENT_ID, SECRET, "radnetprm--backup.sandbox")
    assert captured["url"] == (
        "https://radnetprm--backup.sandbox.my.salesforce.com/services/oauth2/token")


def test_a_request_has_a_timeout(captured):
    salesforce_auth.login_user_flow(CLIENT_ID, SECRET, "example--sandbox.sandbox")
    assert captured["timeout"], "a hung token request would hang every sync behind it"


def test_failed_login_does_not_put_the_secret_in_the_exception(monkeypatch):
    # The case that mattered in practice. The connection-test path prints the
    # exception verbatim, so whatever is in its message reaches the terminal.
    def failing_post(url, data=None, headers=None, timeout=None, **kwargs):
        return _FakeResponse(400, url)

    monkeypatch.setattr(salesforce_auth.requests, "post", failing_post)
    with pytest.raises(requests.HTTPError) as excinfo:
        salesforce_auth.login_user_flow(CLIENT_ID, SECRET, "example--sandbox.sandbox")
    assert SECRET not in str(excinfo.value)
