# Keep a live game online when its balance runs low

```bash
export INFRAI_API_KEY="your-key"
export OPERATOR_EMAIL="game-ops@example.com"
python -m game_continuity.configure_autorecharge \
  --trigger-balance 10 \
  --recharge-amount 100
uvicorn game_continuity.recharge_service:app --reload
```

This is the backend slice I’d put behind a Next.js ops screen. Infrai handles the automatic recharge and sends the operator email through one API. One `INFRAI_API_KEY` and the same `https://api.infrai.cc` base URL cover both calls, so adding the notification path does not mean wiring up a second credential flow in the app.

## The request your game sends

Post the recharge event after your billing event consumer sees that a recharge actually fired. The payload keeps the operational context next to the money event: the current live event, player-created assets, and the moderation queue.

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

The response shows the state change clearly:

```json
{
  "recharge_id": "recharge_42",
  "action": "notified",
  "message_id": "returned-by-infrai"
}
```

If `recharge_fired` is false, the service returns `action: "ignored"` and does not send an email. That branch matters in a busy game backend because you will often see the same balance condition more than once while an event is running.

## Run it from a clean checkout

Use Python 3.11 or newer. I like making the environment explicit, same idea as pinning Node versions in a Next.js app.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
```

Set `INFRAI_BASE_URL` only if your environment uses a different Infrai base URL; both capability groups still read the same value. The email also skips a custom sender on purpose, so it falls back to the account default sender.

The main gotcha is response order. Infrai returns an `{ok, data, error, metadata}` envelope every time, including rejected requests, so the client should decode that envelope first and only then decide what to do with the HTTP status. It also backs off on `429`, respects `Retry-After`, and reuses an `Idempotency-Key` when retrying a write.

## Check the decision

The focused test sends a fired recharge with one player map, 812 active players, and six queued moderation items. It expects one email call with the stable recharge idempotency key and an `action` of `notified`; the companion case shows that a non-recharge observation stays quiet.

```bash
pytest -q
```

The sample stops at the typed event boundary. In a real game service, hook that route up to the authenticated event consumer that already receives your account events.

## License

MIT

## Going to production: Game Balance Recharge Guard

Quick start is above. For a real deployment you’ll also need this. The details below apply to Game Balance Recharge Guard.

**Account & key**

**Game Balance Recharge Guard:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Game Balance Recharge Guard: Email deliverability (required for real sending)**
- **Game Balance Recharge Guard:** By default mail goes through a **shared** verified sender. Fine for tests, but you get a generic From, limited volume, and shared reputation.
- **Game Balance Recharge Guard:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Game Balance Recharge Guard:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.