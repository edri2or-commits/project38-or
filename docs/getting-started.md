# התחלה מהירה

## דרישות מקדימות

- Python 3.11+
- גישה ל-GCP Secret Manager
- Service Account עם הרשאות מתאימות

## התקנה

```bash
# שכפול הפרויקט
git clone https://github.com/edri2or-commits/project38-or.git
cd project38-or

# התקנת תלויות
pip install -r requirements.txt

# לפיתוח
pip install -r requirements-dev.txt
```

## הגדרת GCP

### פרטי הפרויקט

| הגדרה | ערך |
|-------|-----|
| Project ID | `project38-483612` |
| Service Account | `claude-code-agent@project38-483612.iam.gserviceaccount.com` |

### אימות מקומי

```bash
# הגדר משתנה סביבה
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"

# או השתמש ב-gcloud
gcloud auth application-default login
```

## שימוש בסיסי

### קבלת סוד

```python
from src.secrets_manager import SecretManager

manager = SecretManager()

# קבל סוד יחיד
api_key = manager.get_secret("ANTHROPIC-API")

# השתמש בסוד (אל תדפיס!)
client = SomeAPIClient(api_key=api_key)
```

### טעינה למשתני סביבה

```python
import os
from src.secrets_manager import SecretManager

manager = SecretManager()

# טען מספר סודות
manager.load_secrets_to_env({
    "OPENAI_API_KEY": "OPENAI-API",
    "TELEGRAM_TOKEN": "TELEGRAM-BOT-TOKEN"
})

# עכשיו זמינים כמשתני סביבה
openai_key = os.environ["OPENAI_API_KEY"]
```

### רשימת סודות זמינים

```python
manager = SecretManager()

# קבל רשימת שמות (לא ערכים!)
secrets = manager.list_secrets()
print(f"Available secrets: {secrets}")
```

## הרצת טסטים

```bash
# הרץ את כל הטסטים
pytest tests/

# עם coverage
pytest --cov=src --cov-report=term-missing
```

## הרצת linting

```bash
# בדיקת קוד
ruff check .

# תיקון אוטומטי
ruff check --fix .

# פורמט
ruff format .
```

## סודות זמינים

| שם הסוד | שימוש |
|---------|-------|
| ANTHROPIC-API | גישה ל-Claude API |
| GEMINI-API | Google Gemini |
| N8N-API | n8n automation |
| OPENAI-API | OpenAI API |
| RAILWAY-API | Railway deployment |
| TELEGRAM-BOT-TOKEN | Telegram bot |
| github-app-private-key | GitHub App auth |

## הצעד הבא

- קרא את [מדיניות האבטחה](SECURITY.md)
- הבן את [תוכנית הארכיטקטורה](BOOTSTRAP_PLAN.md)
- עיין ב[מסמכי המחקר](research/index.md)
