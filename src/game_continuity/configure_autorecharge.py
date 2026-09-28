from __future__ import annotations

import argparse

from .infrai_client import InfraiClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure the game balance recharge rule")
    parser.add_argument("--trigger-balance", type=float, required=True)
    parser.add_argument("--recharge-amount", type=float, required=True)
    args = parser.parse_args()

    client = InfraiClient.from_env()
    try:
        data = client.configure_autorecharge(
            trigger_balance=args.trigger_balance,
            recharge_amount=args.recharge_amount,
        )
    finally:
        client.close()

    print("Automatic recharge configured:", data)


if __name__ == "__main__":
    main()

