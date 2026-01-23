#!/usr/bin/env python3
"""Run the fixed Smart Email Agent.

This script runs the email agent with direct Gmail API access
(not MCP Gateway which doesn't have REST endpoints).

Usage:
    python scripts/run_email_agent.py
    python scripts/run_email_agent.py --dry-run  # Don't send to Telegram
"""
import sys


def main():
    # Add src to path for imports
    sys.path.insert(0, ".")

    from src.agents.email_agent import EmailAgent

    import argparse
    import logging

    parser = argparse.ArgumentParser(description="Run Smart Email Agent")
    parser.add_argument("--dry-run", action="store_true", help="Don't send to Telegram")
    parser.add_argument("--hours", type=int, default=24, help="Hours to look back")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    print("📧 Smart Email Agent - Fixed Version")
    print("=" * 50)

    agent = EmailAgent()
    result = agent.run(hours=args.hours, send_telegram=not args.dry_run)

    print(f"\n✅ Success: {result.get('success')}")
    print(f"⏱️  Duration: {result.get('duration_ms', 0)}ms")
    print(f"📬 Emails processed: {result.get('emails_processed', 0)}")
    print(f"🔇 System filtered: {result.get('system_filtered', 0)}")
    print(f"🔴 P1 (Urgent): {result.get('p1_count', 0)}")
    print(f"🟠 P2 (Important): {result.get('p2_count', 0)}")
    print(f"🟡 P3 (Info): {result.get('p3_count', 0)}")
    print(f"⚪ P4 (Low): {result.get('p4_count', 0)}")
    print(f"📤 Telegram sent: {result.get('telegram_sent', False)}")

    if result.get("message"):
        print("\n" + "-" * 40)
        print("📝 Message preview:")
        print("-" * 40)
        print(result["message"])
        print("-" * 40)

    if result.get("error"):
        print(f"\n❌ Error: {result['error']}")
        sys.exit(1)

    print("\n✅ Email agent completed successfully!")


if __name__ == "__main__":
    main()
