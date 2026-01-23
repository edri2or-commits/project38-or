#!/usr/bin/env python3
"""Send Phase 3 completion summary to Telegram."""
import os
import httpx

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "5786217215")
    
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        return False
    
    message = """🎉 *Smart Email Agent - Phase 3 Complete!*

📅 23/01/2026

*בדיקות עברו בהצלחה:*
✅ FormExtractor - חילוץ 7 שדות מטופס
✅ DeadlineTracker - זיהוי דדליינים  
✅ UserPreferences - פרופיל 9 שדות
✅ TaskIntegration - יצירת משימות

━━━━━━━━━━━━━━━━━━━━━━

*מודולים חדשים (~4,000 שורות):*
• `form_extractor.py` - טפסי ממשלה ובנקים
• `deadline_tracker.py` - תזכורות לטלגרם
• `user_preferences.py` - למידה מפעולות
• `task_integration.py` - Todoist/Notion

*ADR-014* הושלם! 🚀"""

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    response = httpx.post(url, json={
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }, timeout=30)
    
    if response.status_code == 200:
        print("✅ Message sent successfully!")
        return True
    else:
        print(f"Error: {response.text}")
        return False

if __name__ == "__main__":
    main()
