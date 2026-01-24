#!/usr/bin/env python3
"""Search Gmail for Railway notification emails.

Searches for emails from Railway (railway.app, @railway) and outputs:
1. Total count
2. Date range (oldest to newest)
3. Sample subjects (first 5)
"""
import os
import sys
from datetime import datetime

import httpx


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


def search_railway_emails(access_token: str, max_results: int = 100) -> list[dict]:
    """Search for Railway notification emails."""
    headers = {"Authorization": f"Bearer {access_token}"}

    # Search for Railway emails
    query = "from:railway.app OR from:@railway"

    response = httpx.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages",
        headers=headers,
        params={"q": query, "maxResults": max_results},
        timeout=60,
    )

    if response.status_code != 200:
        print(f"Gmail API error: {response.text}")
        return []

    data = response.json()
    messages = data.get("messages", [])
    total_estimate = data.get("resultSizeEstimate", len(messages))

    print(f"Found approximately {total_estimate} matching emails")
    print(f"Fetching details for {len(messages)} emails...")

    # Get details for each message
    results = []
    for i, msg in enumerate(messages):
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
            date_str = next((h["value"] for h in headers_list if h["name"] == "Date"), "")

            results.append({
                "id": msg["id"],
                "subject": subject,
                "sender": sender,
                "date": date_str,
            })

        if (i + 1) % 20 == 0:
            print(f"  Processed {i + 1}/{len(messages)} emails...")

    return results


def main():
    print("=" * 60)
    print("  Railway Email Search Report")
    print("=" * 60)
    print()

    # Get credentials from environment
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        print("ERROR: Missing Google OAuth credentials")
        sys.exit(1)

    # Refresh access token
    print("Authenticating with Google...")
    try:
        access_token = refresh_google_token(client_id, client_secret, refresh_token)
        print("Authentication successful")
        print()
    except Exception as e:
        print(f"ERROR: Authentication failed: {e}")
        sys.exit(1)

    # Search for Railway emails
    print("Searching for Railway emails...")
    print("Query: from:railway.app OR from:@railway")
    print()

    emails = search_railway_emails(access_token, max_results=100)

    if not emails:
        print()
        print("RESULT: No Railway emails found")
        return

    print()
    print("=" * 60)
    print("  RESULTS")
    print("=" * 60)
    print()

    # 1. Total count
    print(f"1. TOTAL EMAILS FOUND: {len(emails)}")
    print()

    # 2. Date range
    if emails:
        # Parse dates and find range
        dates = []
        for email in emails:
            date_str = email["date"]
            # Gmail dates can have various formats, just store raw string
            dates.append(date_str)

        oldest = emails[-1]["date"] if emails else "N/A"
        newest = emails[0]["date"] if emails else "N/A"

        print("2. DATE RANGE:")
        print(f"   Oldest: {oldest}")
        print(f"   Newest: {newest}")
        print()

    # 3. Sample subjects (first 5)
    print("3. SAMPLE SUBJECTS (first 5):")
    for i, email in enumerate(emails[:5], 1):
        subject = email["subject"]
        # Truncate long subjects
        if len(subject) > 70:
            subject = subject[:67] + "..."
        print(f"   {i}. {subject}")

    print()

    # Additional stats
    print("4. SENDERS BREAKDOWN:")
    senders = {}
    for email in emails:
        sender = email["sender"]
        # Extract just the email address
        if "<" in sender:
            sender = sender.split("<")[1].rstrip(">")
        senders[sender] = senders.get(sender, 0) + 1

    for sender, count in sorted(senders.items(), key=lambda x: -x[1]):
        print(f"   - {sender}: {count} emails")

    print()
    print("=" * 60)
    print("  END OF REPORT")
    print("=" * 60)


if __name__ == "__main__":
    main()
