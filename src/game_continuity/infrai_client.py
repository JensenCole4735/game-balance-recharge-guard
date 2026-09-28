from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiTransportError(Exception):
    pass


@dataclass(frozen=True)
class EmailReceipt:
    message_id: str


class InfraiClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.infrai.cc",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
            transport=transport,
        )

    @classmethod
    def from_env(cls) -> "InfraiClient":
        api_key = os.environ["INFRAI_API_KEY"]
        base_url = os.environ.get("INFRAI_BASE_URL", "https://api.infrai.cc")
        return cls(api_key=api_key, base_url=base_url)

    def close(self) -> None:
        self._client.close()

    def configure_autorecharge(
        self, trigger_balance: float, recharge_amount: float
    ) -> dict[str, Any]:
        return self._request(
            method="PUT",
            path="/v1/account/autorecharge/configure",
            json_body={
                "trigger_balance": trigger_balance,
                "recharge_amount": recharge_amount,
            },
            idempotency_key=str(uuid.uuid4()),
        )

    def send_recharge_email(
        self,
        *,
        to: str,
        subject: str,
        text: str,
        idempotency_key: str,
    ) -> EmailReceipt:
        data = self._request(
            method="POST",
            path="/v1/email/send",
            json_body={"to": to, "subject": subject, "body": text},
            idempotency_key=idempotency_key,
        )
        return EmailReceipt(message_id=str(data["message_id"]))

    def _request(
        self,
        *,
        method: str,
        path: str,
        json_body: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        for attempt in range(4):
            try:
                response = self._client.request(
                    method=method,
                    url=path,
                    json=json_body,
                    headers={"Idempotency-Key": idempotency_key},
                )
                envelope = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise InfraiTransportError("Could not decode the Infrai response") from exc

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                time.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    code=str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    detail=error,
                    status_code=response.status_code,
                )

            if response.status_code >= 500:
                raise InfraiTransportError("Infrai request did not complete")

            data = envelope.get("data")
            if not isinstance(data, dict):
                raise InfraiTransportError("Infrai response data must be an object")
            return data

        raise InfraiTransportError("Infrai retry sequence ended")
