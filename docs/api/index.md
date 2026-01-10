# API Reference

## סקירה מהירה

המודול הראשי לגישה מאובטחת ל-GCP Secret Manager.

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
