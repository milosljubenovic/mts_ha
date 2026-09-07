"""Async API client for moj.mts.rs."""

from __future__ import annotations

import base64
import logging
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
    """Async client for moj.mts.rs with reusable session state."""

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
    def token(self) -> str | None:
        return self._token

    @property
    def username(self) -> str:
        return self._username

    def load_session(self, data: dict[str, Any]) -> None:
        """Restore bearer token from persisted storage."""
        token = data.get("token")
        if token:
            self._token = token
            self._session.headers["Authorization"] = f"Bearer {token}"

    def dump_session(self) -> dict[str, Any]:
        """Serialize session state for persistence."""
        return {
            "token": self._token,
        }

    def _url(self, path: str) -> str:
        return f"{BASE_URL}{path}"

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        auth_retry: bool = True,
    ) -> Any:
        url = URL(self._url(path))
        try:
            async with self._session.request(
                method, url, params=params, json=json
            ) as response:
                if response.status in (
                    HTTPStatus.UNAUTHORIZED,
                    HTTPStatus.FORBIDDEN,
                ) and auth_retry:
                    await self.login()
                    return await self._request_json(
                        method,
                        path,
                        params=params,
                        json=json,
                        auth_retry=False,
                    )
                response.raise_for_status()
                return await response.json()
        except ClientResponseError as err:
            if err.status == HTTPStatus.BAD_REQUEST and auth_retry:
                await self.login()
                return await self._request_json(
                    method,
                    path,
                    params=params,
                    json=json,
                    auth_retry=False,
                )
            if err.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                raise MtsAuthError(f"Authentication failed: {err.status}") from err
            raise MtsApiError(f"API request failed: {err.status} {err.message}") from err

    async def login(self) -> None:
        """Authenticate and obtain a bearer token."""
        payload = {
            "userId": self._username,
            "encodedPassword": encode_password(self._password),
            "rememberMe": True,
        }
        try:
            async with self._session.post(
                URL(self._url(ENDPOINTS["authorize"])),
                json=payload,
            ) as response:
                if response.status == HTTPStatus.BAD_REQUEST:
                    body = await response.text()
                    if "MtsBadCredentialsError" in body:
                        raise MtsAuthError("Invalid username or password")
                    raise MtsApiError(f"Login failed: {body}")
                response.raise_for_status()

            async with self._session.get(URL(self._url(ENDPOINTS["token"]))) as response:
                if response.status == HTTPStatus.INTERNAL_SERVER_ERROR:
                    raise MtsAuthError("Session expired and re-login failed")
                response.raise_for_status()
                data = await response.json()
        except ClientResponseError as err:
            if err.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                raise MtsAuthError("Invalid username or password") from err
            raise MtsApiError(f"Login failed: {err.status}") from err

        token = data.get("token")
        if not token:
            raise MtsApiError("Login succeeded but no token was returned")

        self._token = token
        self._session.headers["Authorization"] = f"Bearer {token}"
        _LOGGER.debug("MTS RS login successful")

    async def validate_session(self) -> bool:
        """Return True when the current session can access account data."""
        if not self._token:
            return False
        try:
            await self._request_json("GET", ENDPOINTS["user"], auth_retry=False)
            return True
        except (MtsAuthError, MtsApiError):
            return False

    async def ensure_logged_in(self) -> None:
        """Reuse an active session or perform a fresh login."""
        if await self.validate_session():
            _LOGGER.debug("Reusing existing MTS RS session")
            return
        await self.login()

    async def get_user(self) -> dict[str, Any]:
        await self.ensure_logged_in()
        return await self._request_json("GET", ENDPOINTS["user"])

    async def get_mobile_services(self) -> list[dict[str, Any]]:
        await self.ensure_logged_in()
        data = await self._request_json("GET", ENDPOINTS["services"])
        services: list[dict[str, Any]] = []
        for group in data.get("serviceGroups", []):
            if group.get("serviceGroupType") != "MOB":
                continue
            for service in group.get("services", []):
                if str(service.get("serviceType", "")).startswith("MOB_"):
                    services.append(service)
        return services

    async def get_msisdn_report(self, msisdn: str) -> dict[str, Any]:
        await self.ensure_logged_in()
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

    async def get_reports(self, msisdns: list[str]) -> dict[str, dict[str, Any]]:
        reports: dict[str, dict[str, Any]] = {}
        for msisdn in msisdns:
            reports[msisdn] = await self.get_msisdn_report(msisdn)
        return reports
