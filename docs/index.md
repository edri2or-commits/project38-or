# Project38-OR

מערכת AI אישית עם אינטגרציה אוטונומית ל-GCP Secret Manager.

## סקירה מהירה

- **גישה אוטונומית** לסודות מ-GCP Secret Manager
- **אבטחה מלאה** - סודות לעולם לא נחשפים
- **Python module** מוכן לשימוש
- **GitHub Actions workflows** אוטומטיים

## התחלה

```python
from src.secrets_manager import SecretManager

manager = SecretManager()

# קבל סוד (בלי לחשוף!)
secret = manager.get_secret("ANTHROPIC-API")

# טען סודות למשתני סביבה
manager.load_secrets_to_env({
    "API_KEY": "OPENAI-API"
})
```

## קישורים מהירים

- [התחלה מהירה](getting-started.md)
- [מדיניות אבטחה](SECURITY.md)
- [תוכנית ארכיטקטורה](BOOTSTRAP_PLAN.md)
