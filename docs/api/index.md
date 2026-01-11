# API Reference

## סקירה כללית

Agent Platform מורכב ממספר רבדים:

### 🌐 FastAPI Application

REST API server לניהול סוכנים ומשימות.

```python
from src.api.main import app
import uvicorn

uvicorn.run(app, host="0.0.0.0", port=8000)
```

[📖 תיעוד מלא →](fastapi.md)

### 💾 Database Layer

PostgreSQL async connection management עם SQLModel.

```python
from src.api.database import get_session, create_db_and_tables

await create_db_and_tables()
```

[📖 תיעוד מלא →](database.md)

### 📦 Data Models

SQLModel schemas עבור Agent ו-Task entities.

```python
from src.models import Agent, Task

agent = Agent(
    name="Stock Monitor",
    description="עוקב אחרי מניות",
    code="# Generated code",
    status="active"
)
```

[📖 תיעוד מלא →](models.md)

### 🏭 Agent Factory (Phase 3.2)

ייצור אוטומטי של סוכנים מתיאור בשפה טבעית.

```python
from src.factory.generator import generate_agent_code
from src.factory.ralph_loop import ralph_wiggum_loop

# יצירת קוד מתיאור
result = await generate_agent_code(
    description="צור סוכן שעוקב אחרי מניות של טסלה"
)

# תיקון ואימות אוטומטי
validated = await ralph_wiggum_loop(result['code'])
```

[📖 תיעוד מלא →](factory.md)

### 🔐 Secret Management

גישה מאובטחת ל-GCP Secret Manager.

```python
from src.secrets_manager import SecretManager

manager = SecretManager()
secret = manager.get_secret("ANTHROPIC-API")
```

### 🔧 GitHub Operations

אוטומציה של GitHub PRs וסימולציות.

- [GitHub Authentication](github_auth.md) - WIF-based authentication
- [GitHub PR Operations](github_pr.md) - Universal PR creation

---

## SecretManager API

### סקירה מהירה

גישה מאובטחת ל-GCP Secret Manager ללא שמירת סודות בקוד.

```python
from src.secrets_manager import SecretManager

manager = SecretManager()
secret = manager.get_secret("ANTHROPIC-API")
```

!!! warning "אזהרה"
    לעולם אל תדפיס או תרשום ערכי סודות!

---

## SecretManager Class

::: src.secrets_manager.SecretManager
    options:
      show_root_heading: true
      heading_level: 3
      members:
        - __init__
        - get_secret
        - list_secrets
        - verify_access
        - load_secrets_to_env
        - clear_cache

---

## Convenience Functions

::: src.secrets_manager.get_secret
    options:
      show_root_heading: true
      heading_level: 3

---

## דוגמאות שימוש

### שליפת סוד בודד

```python
from src.secrets_manager import SecretManager

manager = SecretManager()
api_key = manager.get_secret("ANTHROPIC-API")

# השתמש בסוד (אל תדפיס!)
client = SomeAPIClient(api_key=api_key)
```

### טעינה למשתני סביבה

```python
import os
from src.secrets_manager import SecretManager

manager = SecretManager()
manager.load_secrets_to_env({
    "OPENAI_API_KEY": "OPENAI-API",
    "TELEGRAM_TOKEN": "TELEGRAM-BOT-TOKEN"
})

# עכשיו זמינים כמשתני סביבה
openai_key = os.environ["OPENAI_API_KEY"]
```

### ניקוי אחרי שימוש

```python
manager = SecretManager()
secret = manager.get_secret("some-secret")

# ... use secret ...

# נקה מהזיכרון
del secret
manager.clear_cache()
```
