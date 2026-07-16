import smtplib
from unittest.mock import MagicMock, patch

import httpx
import pytest

from apps.core import ms365_smtp


@pytest.fixture(autouse=True)
def _clear_token_cache():
    from django.core.cache import cache

    cache.delete(ms365_smtp._TOKEN_CACHE_KEY)
    yield
    cache.delete(ms365_smtp._TOKEN_CACHE_KEY)


@pytest.fixture
def ms365_settings(settings):
    settings.MS365_TENANT_ID = "tenant-123"
    settings.MS365_CLIENT_ID = "client-456"
    settings.MS365_CLIENT_SECRET = "secret-789"
    settings.MS365_SMTP_USER = "noreply@example.com"
    return settings


class TestIsEnabled:
    def test_true_when_all_settings_present(self, ms365_settings):
        assert ms365_smtp.is_enabled() is True

    def test_false_when_client_secret_missing(self, ms365_settings):
        ms365_settings.MS365_CLIENT_SECRET = ""
        assert ms365_smtp.is_enabled() is False


class TestGetAccessToken:
    def test_raises_when_not_configured(self, settings):
        settings.MS365_TENANT_ID = ""
        settings.MS365_CLIENT_ID = ""
        settings.MS365_CLIENT_SECRET = ""
        with pytest.raises(ms365_smtp.MS365TokenError):
            ms365_smtp.get_access_token()

    def test_success_caches_and_returns_token(self, ms365_settings):
        response = httpx.Response(
            200, json={"token_type": "Bearer", "expires_in": 3599, "access_token": "abc123"}
        )
        with patch.object(ms365_smtp.httpx, "post", return_value=response) as mock_post:
            token = ms365_smtp.get_access_token()

        assert token == "abc123"
        request_kwargs = mock_post.call_args.kwargs
        assert request_kwargs["data"]["grant_type"] == "client_credentials"
        assert request_kwargs["data"]["client_id"] == "client-456"
        assert request_kwargs["data"]["client_secret"] == "secret-789"
        assert request_kwargs["data"]["scope"] == "https://outlook.office365.com/.default"
        assert (
            mock_post.call_args.args[0]
            == "https://login.microsoftonline.com/tenant-123/oauth2/v2.0/token"
        )

    def test_second_call_uses_cache_not_a_new_request(self, ms365_settings):
        response = httpx.Response(
            200, json={"token_type": "Bearer", "expires_in": 3599, "access_token": "abc123"}
        )
        with patch.object(ms365_smtp.httpx, "post", return_value=response) as mock_post:
            first = ms365_smtp.get_access_token()
            second = ms365_smtp.get_access_token()

        assert first == second == "abc123"
        mock_post.assert_called_once()

    def test_force_refresh_bypasses_cache(self, ms365_settings):
        responses = [
            httpx.Response(
                200, json={"token_type": "Bearer", "expires_in": 3599, "access_token": "first"}
            ),
            httpx.Response(
                200, json={"token_type": "Bearer", "expires_in": 3599, "access_token": "second"}
            ),
        ]
        with patch.object(ms365_smtp.httpx, "post", side_effect=responses) as mock_post:
            first = ms365_smtp.get_access_token()
            second = ms365_smtp.get_access_token(force_refresh=True)

        assert (first, second) == ("first", "second")
        assert mock_post.call_count == 2

    def test_error_response_raises_with_description(self, ms365_settings):
        response = httpx.Response(
            400,
            json={
                "error": "invalid_client",
                "error_description": "AADSTS7000215: Invalid client secret provided.",
            },
        )
        with patch.object(ms365_smtp.httpx, "post", return_value=response):
            with pytest.raises(ms365_smtp.MS365TokenError, match="Invalid client secret"):
                ms365_smtp.get_access_token()

    def test_network_failure_raises_ms365_token_error(self, ms365_settings):
        with patch.object(ms365_smtp.httpx, "post", side_effect=httpx.ConnectError("boom")):
            with pytest.raises(ms365_smtp.MS365TokenError):
                ms365_smtp.get_access_token()


class TestBuildXoauth2String:
    def test_matches_microsoft_documented_format(self):
        result = ms365_smtp.build_xoauth2_string("user@example.com", "TOKEN123")
        assert result == "user=user@example.com\x01auth=Bearer TOKEN123\x01\x01"


class TestMicrosoft365EmailBackendAuth:
    def _backend(self, ms365_settings):
        from django.conf import settings as django_settings

        django_settings.EMAIL_HOST_USER = "noreply@example.com"
        django_settings.EMAIL_HOST = "smtp.office365.com"
        django_settings.EMAIL_PORT = 587
        django_settings.EMAIL_USE_TLS = True
        django_settings.EMAIL_USE_SSL = False
        return ms365_smtp.Microsoft365EmailBackend()

    def test_open_authenticates_with_xoauth2_not_login(self, ms365_settings):
        backend = self._backend(ms365_settings)
        fake_smtp = MagicMock()
        fake_smtp.auth.return_value = (235, b"2.7.0 Authentication successful")

        with (
            patch.object(ms365_smtp.httpx, "post") as mock_post,
            patch.object(
                ms365_smtp.Microsoft365EmailBackend,
                "connection_class",
                new=MagicMock(return_value=fake_smtp),
            ),
        ):
            mock_post.return_value = httpx.Response(
                200, json={"token_type": "Bearer", "expires_in": 3599, "access_token": "tok"}
            )
            result = backend.open()

        assert result is True
        fake_smtp.starttls.assert_called_once()
        fake_smtp.login.assert_not_called()
        fake_smtp.auth.assert_called_once()
        auth_args = fake_smtp.auth.call_args
        assert auth_args.args[0] == "XOAUTH2"
        assert auth_args.kwargs["initial_response_ok"] is False
        authobject = auth_args.args[1]
        assert authobject() == "user=noreply@example.com\x01auth=Bearer tok\x01\x01"

    def test_open_retries_once_on_stale_cached_token(self, ms365_settings):
        backend = self._backend(ms365_settings)
        fake_smtp = MagicMock()
        fake_smtp.auth.side_effect = [
            smtplib.SMTPAuthenticationError(535, b"5.7.3 Authentication unsuccessful"),
            (235, b"2.7.0 Authentication successful"),
        ]
        responses = [
            httpx.Response(
                200, json={"token_type": "Bearer", "expires_in": 3599, "access_token": "stale"}
            ),
            httpx.Response(
                200, json={"token_type": "Bearer", "expires_in": 3599, "access_token": "fresh"}
            ),
        ]

        with (
            patch.object(ms365_smtp.httpx, "post", side_effect=responses),
            patch.object(
                ms365_smtp.Microsoft365EmailBackend,
                "connection_class",
                new=MagicMock(return_value=fake_smtp),
            ),
        ):
            # Prime the cache with the "stale" token first.
            ms365_smtp.get_access_token()
            result = backend.open()

        assert result is True
        assert fake_smtp.auth.call_count == 2

    def test_open_gives_up_after_one_retry(self, ms365_settings):
        backend = self._backend(ms365_settings)
        fake_smtp = MagicMock()
        fake_smtp.auth.side_effect = smtplib.SMTPAuthenticationError(
            535, b"5.7.3 Authentication unsuccessful"
        )
        response = httpx.Response(
            200, json={"token_type": "Bearer", "expires_in": 3599, "access_token": "tok"}
        )

        with (
            patch.object(ms365_smtp.httpx, "post", return_value=response),
            patch.object(
                ms365_smtp.Microsoft365EmailBackend,
                "connection_class",
                new=MagicMock(return_value=fake_smtp),
            ),
            pytest.raises(smtplib.SMTPAuthenticationError),
        ):
            backend.open()

        assert fake_smtp.auth.call_count == 2
