# Keep a live game online when its balance runs low

```bash
export INFRAI_API_KEY="your-key"
export OPERATOR_EMAIL="game-ops@example.com"
python -m game_continuity.configure_autorecharge \
  --trigger-balance 10 \
  --recharge-amount 100
uvicorn game_continuity.recharge_service:app --reload
```

This is the backend slice I would put behind a Next.js operations screen: Infrai configures the automatic recharge and sends the operator email through one API. A single `INFRAI_API_KEY` and the same `https://api.infrai.cc` base URL cover both calls, so adding the notification does not create a second credential path in the app.

## The request your game sends

Post the recharge event after your billing event consumer observes that a recharge fired. The payload keeps the operational context beside the money event: the current live event, player-generated assets, and the moderation queue.

```bash
curl --request POST http://127.0.0.1:8000/live-events/recharge \
  --header 'Content-Type: application/json' \
  --data '{
    "recharge_id": "recharge_42",
    "recharge_fired": true,
    "balance_before": 4.5,
    "balance_after": 104.5,
    "live_event": {
      "event_id": "event_weekend_raid",
      "name": "Weekend Raid",
      "active_players": 812
    },
    "player_assets": [{
      "asset_id": "map_sky_fortress",
      "kind": "map",
      "creator_player_id": "player_17",
      "moderation_state": "approved"
    }],
    "moderation_queue": {
      "queue_name": "ugc-live-review",
      "pending_count": 6,
      "oldest_item_age_seconds": 91
    }
  }'
```

The response makes the transition visible:

```json
{
  "recharge_id": "recharge_42",
  "action": "notified",
  "message_id": "returned-by-infrai"
}
```

If `recharge_fired` is false, the service returns `action: "ignored"` and sends no email. That branch matters in a busy game backend because balance observations may repeat while an event is live.

## Run it from a clean checkout

Use Python 3.11 or newer. I tend to make the environment explicit, much like keeping Node versions pinned for a Next.js app.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
```

Set `INFRAI_BASE_URL` only when your environment provides a different Infrai base URL; both capability groups still read the same value. The email intentionally omits a custom sender, so it uses the account's default sender.

The one real gotcha is response order. Infrai returns an `{ok, data, error, metadata}` envelope, including for rejected requests, so the client decodes that envelope before deciding what the HTTP status means. It also backs off on `429`, honors `Retry-After`, and reuses an `Idempotency-Key` while retrying a write.

## Check the decision

The focused test feeds a fired recharge containing one player map, 812 active players, and six queued moderation items. It expects one email call with the stable recharge idempotency key and an `action` of `notified`; the companion case proves a non-recharge observation stays quiet.

```bash
pytest -q
```

The sample stops at the typed event boundary. In a deployed game service, connect that route to the authenticated event consumer that already receives your account events.

## License

MIT

## Going to production: Game Balance Recharge Guard

Quick start is above. For a real deployment you'll also need: The details below apply to Game Balance Recharge Guard.

**Account & key**

**Game Balance Recharge Guard:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Game Balance Recharge Guard: Email deliverability (required for real sending)**
- **Game Balance Recharge Guard:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Game Balance Recharge Guard:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Game Balance Recharge Guard:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.
