from game_continuity.infrai_client import EmailReceipt
from game_continuity.recharge_service import RechargeEvent, handle_recharge


class RecordingGateway:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def send_recharge_email(
        self,
        *,
        to: str,
        subject: str,
        text: str,
        idempotency_key: str,
    ) -> EmailReceipt:
        self.calls.append(
            {
                "to": to,
                "subject": subject,
                "text": text,
                "idempotency_key": idempotency_key,
            }
        )
        return EmailReceipt(message_id="msg_recharge_42")


def recharge_event(fired: bool) -> RechargeEvent:
    return RechargeEvent.model_validate(
        {
            "recharge_id": "recharge_42",
            "recharge_fired": fired,
            "balance_before": 4.5,
            "balance_after": 104.5 if fired else 4.5,
            "live_event": {
                "event_id": "event_weekend_raid",
                "name": "Weekend Raid",
                "active_players": 812,
            },
            "player_assets": [
                {
                    "asset_id": "map_sky_fortress",
                    "kind": "map",
                    "creator_player_id": "player_17",
                    "moderation_state": "approved",
                }
            ],
            "moderation_queue": {
                "queue_name": "ugc-live-review",
                "pending_count": 6,
                "oldest_item_age_seconds": 91,
            },
        }
    )


def test_recharge_event_sends_one_deduplicated_operator_notice() -> None:
    gateway = RecordingGateway()

    decision = handle_recharge(recharge_event(True), gateway, "ops@example.com")

    assert decision.action == "notified"
    assert decision.message_id == "msg_recharge_42"
    assert len(gateway.calls) == 1
    assert gateway.calls[0]["idempotency_key"] == "recharge-notice-recharge_42"
    assert "812 active players" in gateway.calls[0]["text"]
    assert "6 items await moderation" in gateway.calls[0]["text"]


def test_non_recharge_event_does_not_page_the_operator() -> None:
    gateway = RecordingGateway()

    decision = handle_recharge(recharge_event(False), gateway, "ops@example.com")

    assert decision.action == "ignored"
    assert decision.message_id is None
    assert gateway.calls == []

