"""Async API client for moj.mts.rs."""

from __future__ import annotations

import base64
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from http import HTTPStatus
from typing import Any

import aiohttp
from aiohttp import ClientResponseError
from yarl import URL

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://moj.mts.rs"

ENDPOINTS = {
    "authorize": "/selfcare/b2c/user/authorize",
    "token": "/selfcare/b2c/auth/token",
    "logout": "/selfcare/b2c/user/logout",
    "user": "/hybris/mtscommercewebservices/v2/mtsB2CSelfcare/users/current",
    "services": (
        "/hybris/mtscommercewebservices/v2/mtsB2CSelfcare/"
        "selfcare/users/current/services/groups?scv2=true"
    ),
    "mobile_details": (
        "/hybris/mtscommercewebservices/v2/mtsB2CSelfcare/"
        "selfcare/mobileservices/users/current/details"
    ),
    "active_addons": (
        "/hybris/mtscommercewebservices/v2/mtsB2CSelfcare/"
        "selfcare/users/current/addons/active"
    ),
}

DEFAULT_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/json",
    "language": "1",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


class MtsAuthError(Exception):
    """Raised when authentication fails."""


class MtsApiError(Exception):
    """Raised for other API failures."""

    def __init__(
        self, message: str, *, retry_after: float | None = None
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def encode_password(password: str) -> str:
    """Encode password the same way the moj.mts.rs web portal does."""
    encoded = base64.b64encode(password.encode("utf-8")).decode("ascii")
    return f"<b64>{encoded}</b64>"


def extract_internet_bonuses(details: dict[str, Any]) -> list[dict[str, Any]]:
    """Return internet bonus entries from mobile details."""
    bonuses: list[dict[str, Any]] = []
    for bonus in details.get("bonuses", []):
        description = str(bonus.get("description", ""))
        if "internet" not in description.lower():
            continue
        bonuses.append(
            {
                "description": description,
                "remaining": bonus.get("total"),
                "remaining_formatted": bonus.get("totalFormatted"),
                "unit": bonus.get("unit"),
                "expires": bonus.get("expireDate"),
            }
        )
    return bonuses


def extract_internet_packages(addons: dict[str, Any]) -> list[dict[str, Any]]:
    """Return active internet packages from addon data."""
    packages: list[dict[str, Any]] = []
    for category in addons.get("categories", []):
        code = str(category.get("code", ""))
        name = str(category.get("name", ""))
        if "internet" not in code.lower() and "internet" not in name.lower():
            continue
        for item in category.get("activated", []):
            packages.append(
                {
                    "name": item.get("name", ""),
                    "start_date": item.get("startDate", ""),
                    "end_date": item.get("endDate", ""),
                    "auto_renew": bool(item.get("autoRenew", False)),
                    "category": name or code,
                }
            )
    return packages


def build_msisdn_report(
    msisdn: str,
    details: dict[str, Any],
    addons: dict[str, Any],
) -> dict[str, Any]:
    """Build a normalized report for one phone number."""
    internet_bonuses = extract_internet_bonuses(details)
    internet_packages = extract_internet_packages(addons)
    primary_bonus = internet_bonuses[0] if internet_bonuses else {}
    primary_package = internet_packages[0] if internet_packages else {}

    return {
        "msisdn": msisdn,
        "msisdn_formatted": details.get("msisdnFormatted"),
        "balance": details.get("balance"),
        "balance_formatted": details.get("balanceFormatted"),
        "credit_expires": details.get("creditExpireDate"),
        "sim_expires": details.get("simExpireDate"),
        "internet_remaining": primary_bonus.get("remaining"),
        "internet_remaining_formatted": primary_bonus.get("remaining_formatted"),
        "internet_unit": primary_bonus.get("unit"),
        "internet_expires": primary_bonus.get("expires"),
        "internet_bonuses": internet_bonuses,
        "package_name": primary_package.get("name"),
        "package_start": primary_package.get("start_date"),
        "package_end": primary_package.get("end_date"),
        "package_auto_renew": primary_package.get("auto_renew"),
        "internet_packages": internet_packages,
    }


class MtsApiClient:
    """Async client for moj.mts.rs using short-lived login sessions."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._token: str | None = None

    @property
    def username(self) -> str:
        return self._username

    def set_credentials(self, username: str, password: str) -> None:
        """Update credentials used for the next login."""
        self._username = username
        self._password = password
        self._token = None

    def _url(self, path: str) -> str:
        return f"{BASE_URL}{path}"

    def _request_headers(
        self,
        *,
        authenticated: bool = True,
        json_body: bool = False,
    ) -> dict[str, str]:
        """Build per-request headers for HA's shared aiohttp session."""
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "language": "1",
            "User-Agent": DEFAULT_HEADERS["User-Agent"],
        }
        if json_body:
            headers["Content-Type"] = "application/json"
        if authenticated and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        url = URL(self._url(path))
        try:
            async with self._session.request(
                method,
                url,
                params=params,
                json=json,
                headers=self._request_headers(json_body=json is not None),
            ) as response:
                response.raise_for_status()
                return await response.json()
        except ClientResponseError as err:
            if err.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                raise MtsAuthError(f"Authentication failed: {err.status}") from err
            raise MtsApiError(f"API request failed: {err.status} {err.message}") from err
        except (aiohttp.ClientConnectorError, aiohttp.ServerTimeoutError) as err:
            _LOGGER.error("MTS RS request failed for %s %s: %s", method, path, err)
            raise MtsApiError(f"Connection failed: {err}") from err

    def _reset_session_state(self) -> None:
        """Clear auth state before starting a new portal session."""
        self._token = None
        with suppress(AttributeError):
            self._session.cookie_jar.clear()

    async def login(self) -> None:
        """Authenticate and obtain a bearer token."""
        self._reset_session_state()
        payload = {
            "userId": self._username,
            "encodedPassword": encode_password(self._password),
            "rememberMe": True,
        }
        try:
            async with self._session.post(
                URL(self._url(ENDPOINTS["authorize"])),
                json=payload,
                headers=self._request_headers(authenticated=False, json_body=True),
            ) as response:
                if response.status == HTTPStatus.BAD_REQUEST:
                    body = await response.text()
                    if "MtsBadCredentialsError" in body:
                        raise MtsAuthError("Invalid username or password")
                    if "nedostupan" in body.lower():
                        raise MtsApiError(
                            "MTS service is temporarily unavailable. Try again later.",
                            retry_after=300,
                        )
                    raise MtsApiError(f"Login failed: {body}")
                response.raise_for_status()

            async with self._session.get(
                URL(self._url(ENDPOINTS["token"])),
                headers=self._request_headers(authenticated=False),
            ) as response:
                if response.status == HTTPStatus.INTERNAL_SERVER_ERROR:
                    raise MtsAuthError("Session expired and re-login failed")
                response.raise_for_status()
                data = await response.json()
        except ClientResponseError as err:
            if err.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                raise MtsAuthError("Invalid username or password") from err
            raise MtsApiError(f"Login failed: {err.status}") from err
        except (aiohttp.ClientConnectorError, aiohttp.ServerTimeoutError) as err:
            _LOGGER.error("MTS RS login request failed: %s", err)
            raise MtsApiError(f"Connection failed: {err}") from err

        token = data.get("token")
        if not token:
            raise MtsApiError("Login succeeded but no token was returned")

        self._token = token
        _LOGGER.debug("MTS RS login successful")

    async def logout(self) -> None:
        """End the current portal session."""
        if not self._token:
            return
        try:
            async with self._session.post(
                URL(self._url(ENDPOINTS["logout"])),
                headers=self._request_headers(),
            ) as response:
                if response.status >= HTTPStatus.BAD_REQUEST:
                    _LOGGER.debug("MTS RS logout returned status %s", response.status)
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("MTS RS logout failed (ignored): %s", err)
        finally:
            self._reset_session_state()

    @asynccontextmanager
    async def authenticated(self) -> AsyncIterator[MtsApiClient]:
        """Log in, yield the client, then log out."""
        await self.login()
        try:
            yield self
        finally:
            await self.logout()

    async def fetch_mobile_services(self) -> list[dict[str, Any]]:
        """Log in, discover mobile services, and log out."""
        async with self.authenticated():
            return await self._get_mobile_services()

    async def fetch_reports(self, msisdns: list[str]) -> dict[str, dict[str, Any]]:
        """Log in, fetch all configured numbers, and log out."""
        async with self.authenticated():
            reports: dict[str, dict[str, Any]] = {}
            for msisdn in msisdns:
                reports[msisdn] = await self._get_msisdn_report(msisdn)
            return reports

    async def _get_mobile_services(self) -> list[dict[str, Any]]:
        data = await self._request_json("GET", ENDPOINTS["services"])
        services: list[dict[str, Any]] = []
        for group in data.get("serviceGroups", []):
            if group.get("serviceGroupType") != "MOB":
                continue
            for service in group.get("services", []):
                if str(service.get("serviceType", "")).startswith("MOB_"):
                    services.append(service)
        return services

    async def _get_msisdn_report(self, msisdn: str) -> dict[str, Any]:
        details = await self._request_json(
            "GET",
            ENDPOINTS["mobile_details"],
            params={"msisdn": msisdn, "scv2": "true"},
        )
        addons = await self._request_json(
            "GET",
            ENDPOINTS["active_addons"],
            params={"msisdn": msisdn},
        )
        return build_msisdn_report(msisdn, details, addons)
