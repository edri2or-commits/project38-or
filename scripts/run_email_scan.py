#!/usr/bin/env python3
"""Direct Gmail scan and Telegram notification.

Scans Gmail directly using OAuth credentials and sends summary to Telegram.
Bypasses MCP protocol issues by using direct API calls.
"""
import json
import os
import sys
from datetime import datetime, timezone

import httpx


def get_gmail_messages(access_token: str, hours: int = 24) -> list[dict]:
    """Fetch unread emails from Gmail."""
    headers = {"Authorization": f"Bearer {access_token}"}

    # Search for unread emails
    query = f"is:unread newer_than:{hours}h"

    response = httpx.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages",
        headers=headers,
        params={"q": query, "maxResults": 50},
        timeout=30,
    )

    if response.status_code != 200:
        print(f"Gmail API error: {response.text}")
        return []

    data = response.json()
    messages = data.get("messages", [])

    # Get details for each message
    results = []
    for msg in messages[:20]:  # Limit to 20
        msg_response = httpx.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg['id']}",
            headers=headers,
            params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
            timeout=30,
        )

        if msg_response.status_code == 200:
            msg_data = msg_response.json()
            headers_list = msg_data.get("payload", {}).get("headers", [])

            subject = next((h["value"] for h in headers_list if h["name"] == "Subject"), "")
            sender = next((h["value"] for h in headers_list if h["name"] == "From"), "")
            date = next((h["value"] for h in headers_list if h["name"] == "Date"), "")
            snippet = msg_data.get("snippet", "")

            results.append({
                "id": msg["id"],
                "subject": subject,
                "sender": sender,
                "date": date,
                "snippet": snippet,
            })

    return results


def classify_email(email: dict) -> tuple[str, str]:
    """Classify email by priority and category."""
    subject = email["subject"].lower()
    sender = email["sender"].lower()
    snippet = email["snippet"].lower()

    # P1 - Urgent
    if any(kw in subject or kw in snippet for kw in [
        "דחוף", "urgent", "asap", "מיידי", "חשוב מאוד",
        "ביטוח לאומי", "מס הכנסה", "בנק", "תשלום", "חוב"
    ]):
        if "ביטוח לאומי" in sender or "btl.gov.il" in sender:
            return "P1", "בירוקרטיה"
        if "בנק" in sender or "bank" in sender:
            return "P1", "כספים"
        return "P1", "דחוף"

    # P2 - Important
    if any(kw in subject or kw in snippet for kw in [
        "פגישה", "meeting", "תזכורת", "reminder", "אישור", "confirm"
    ]):
        return "P2", "יומן"

    # P3 - Normal
    if any(kw in subject or kw in snippet for kw in [
        "newsletter", "עדכון", "update", "הודעה"
    ]):
        return "P3", "מידע"

    # P4 - Low
    if any(kw in subject or kw in snippet for kw in [
        "הנחה", "sale", "מבצע", "promotion"
    ]):
        return "P4", "פרסום"

    return "P3", "מידע"


def format_telegram_message(emails: list[dict]) -> str:
    """Format emails as Telegram message."""
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")

    # Classify emails
    classified = []
    for email in emails:
        priority, category = classify_email(email)
        classified.append((email, priority, category))

    # Count by priority
    p1 = [e for e in classified if e[1] == "P1"]
    p2 = [e for e in classified if e[1] == "P2"]
    p3 = [e for e in classified if e[1] == "P3"]
    p4 = [e for e in classified if e[1] == "P4"]

    lines = [
        f"🌅 *סיכום מיילים - {now}*",
        "",
        f"📊 *סטטיסטיקה:*",
        f"• {len(emails)} מיילים חדשים",
        f"• 🔴 דחוף: {len(p1)} | 🟠 חשוב: {len(p2)}",
        f"• 🟡 מידע: {len(p3)} | ⚪ פרסום: {len(p4)}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    # P1 - Urgent
    if p1:
        lines.append("")
        lines.append("🔴 *דחוף (P1):*")
        for email, _, category in p1[:5]:
            sender_name = email["sender"].split("<")[0].strip()
            subject = email["subject"][:40] + ("..." if len(email["subject"]) > 40 else "")
            lines.append(f"  • [{category}] *{sender_name}*")
            lines.append(f"    {subject}")

    # P2 - Important
    if p2:
        lines.append("")
        lines.append("🟠 *חשוב (P2):*")
        for email, _, category in p2[:5]:
            sender_name = email["sender"].split("<")[0].strip()
            subject = email["subject"][:40] + ("..." if len(email["subject"]) > 40 else "")
            lines.append(f"  • *{sender_name}*: {subject}")

    # P3 - Show details (not just summary)
    if p3:
        lines.append("")
        lines.append("🟡 *מידע (P3):*")
        for email, _, category in p3[:7]:
            sender_name = email["sender"].split("<")[0].strip()[:25]
            subject = email["subject"][:35] + ("..." if len(email["subject"]) > 35 else "")
            lines.append(f"  • {sender_name}")
            lines.append(f"    _{subject}_")

    # P4 - Promotions (summary only)
    if p4:
        lines.append("")
        lines.append(f"⚪ *פרסום:* {len(p4)} מיילים")

    if not emails:
        lines = [
            f"🌅 *סיכום מיילים - {now}*",
            "",
            "✅ *אין מיילים חדשים!*",
            "_תיבה נקייה - יום טוב!_"
        ]

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("_Smart Email Agent - Phase 3_")

    return "\n".join(lines)


def send_telegram(message: str, token: str, chat_id: str) -> bool:
    """Send message to Telegram."""
    response = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
        },
        timeout=30,
    )

    if response.status_code == 200:
        print("✅ Telegram message sent!")
        return True
    else:
        print(f"❌ Telegram error: {response.text}")
        return False


def refresh_google_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Refresh Google OAuth token."""
    response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )

    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"Token refresh failed: {response.text}")


def main():
    print("📧 Smart Email Agent - Direct Scan")
    print("=" * 50)

    # Get credentials from environment
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN")
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not all([client_id, client_secret, refresh_token]):
        print("❌ Missing Google OAuth credentials")
        sys.exit(1)

    if not all([telegram_token, telegram_chat_id]):
        print("❌ Missing Telegram credentials")
        sys.exit(1)

    # Refresh access token
    print("🔐 Refreshing Google token...")
    try:
        access_token = refresh_google_token(client_id, client_secret, refresh_token)
        print("✅ Token refreshed")
    except Exception as e:
        print(f"❌ Token refresh failed: {e}")
        sys.exit(1)

    # Fetch emails
    print("📬 Fetching emails...")
    emails = get_gmail_messages(access_token, hours=24)
    print(f"✅ Found {len(emails)} emails")

    # Format message
    message = format_telegram_message(emails)
    print("\n📝 Message preview:")
    print("-" * 40)
    print(message)
    print("-" * 40)

    # Send to Telegram
    print("\n📤 Sending to Telegram...")
    success = send_telegram(message, telegram_token, telegram_chat_id)

    if success:
        print("\n✅ Email scan complete!")
    else:
        print("\n❌ Failed to send Telegram message")
        sys.exit(1)


if __name__ == "__main__":
    main()
