from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Iterator, Literal, Protocol

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from .infrai_client import EmailReceipt, InfraiClient, InfraiError, InfraiTransportError


class PlayerAsset(BaseModel):
    asset_id: str
    kind: Literal["skin", "map", "quest", "item"]
    creator_player_id: str
    moderation_state: Literal["pending", "approved", "rejected"]


class ModerationQueue(BaseModel):
    queue_name: str
    pending_count: int = Field(ge=0)
    oldest_item_age_seconds: int = Field(ge=0)


class LiveEvent(BaseModel):
    event_id: str
    name: str
    active_players: int = Field(ge=0)


class RechargeEvent(BaseModel):
    recharge_id: str
    recharge_fired: bool
    balance_before: float = Field(ge=0)
    balance_after: float = Field(ge=0)
    live_event: LiveEvent
    player_assets: list[PlayerAsset]
    moderation_queue: ModerationQueue


class RechargeDecision(BaseModel):
    recharge_id: str
    action: Literal["notified", "ignored"]
    message_id: str | None = None


class NotificationGateway(Protocol):
    def send_recharge_email(
        self,
        *,
        to: str,
        subject: str,
        text: str,
        idempotency_key: str,
    ) -> EmailReceipt:
        raise AssertionError("Protocol declarations are not called directly")


def handle_recharge(
    event: RechargeEvent,
    gateway: NotificationGateway,
    operator_email: str,
) -> RechargeDecision:
    if not event.recharge_fired:
        return RechargeDecision(recharge_id=event.recharge_id, action="ignored")

    receipt = gateway.send_recharge_email(
        to=operator_email,
        subject=f"Recharge kept {event.live_event.name} online",
        text=(
            f"Recharge {event.recharge_id} completed. "
            f"Balance moved from {event.balance_before:.2f} to {event.balance_after:.2f}. "
            f"The live event has {event.live_event.active_players} active players, "
            f"{len(event.player_assets)} player assets are in this snapshot, and "
            f"{event.moderation_queue.pending_count} items await moderation."
        ),
        idempotency_key=f"recharge-notice-{event.recharge_id}",
    )
    return RechargeDecision(
        recharge_id=event.recharge_id,
        action="notified",
        message_id=receipt.message_id,
    )


def create_app(client: InfraiClient | None = None) -> FastAPI:
    owned_client = client

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> Iterator[None]:
        yield
        if client is None and owned_client is not None:
            owned_client.close()

    app = FastAPI(title="Game Balance Guard", lifespan=lifespan)

    def get_gateway() -> NotificationGateway:
        nonlocal owned_client
        if owned_client is None:
            owned_client = InfraiClient.from_env()
        return owned_client

    @app.post("/live-events/recharge", response_model=RechargeDecision)
    def recharge_route(
        event: RechargeEvent,
        gateway: NotificationGateway = Depends(get_gateway),
    ) -> RechargeDecision:
        try:
            return handle_recharge(
                event=event,
                gateway=gateway,
                operator_email=os.environ["OPERATOR_EMAIL"],
            )
        except InfraiError as exc:
            status_code = exc.status_code if 400 <= exc.status_code < 500 else 502
            raise HTTPException(status_code=status_code, detail=exc.detail) from exc
        except InfraiTransportError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return app


app = create_app()
