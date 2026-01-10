# API Reference

## SecretManager

המודול הראשי לגישה מאובטחת ל-GCP Secret Manager.

### Class: SecretManager

```python
from src.secrets_manager import SecretManager

manager = SecretManager(project_id: str | None = None)
```

**Parameters:**

| פרמטר | טיפוס | ברירת מחדל | תיאור |
|-------|-------|-------------|-------|
| `project_id` | `str \| None` | `"project38-483612"` | GCP Project ID |

### Methods

#### get_secret

```python
def get_secret(self, secret_id: str, version: str = "latest") -> str | None
```

שליפת סוד מ-Secret Manager.

**Parameters:**

| פרמטר | טיפוס | ברירת מחדל | תיאור |
|-------|-------|-------------|-------|
| `secret_id` | `str` | - | שם הסוד |
| `version` | `str` | `"latest"` | גרסה לשליפה |

**Returns:** `str | None` - ערך הסוד או None אם לא נמצא

!!! warning "אזהרה"
    לעולם אל תדפיס או תרשום את הערך המוחזר!

---

#### list_secrets

```python
def list_secrets(self) -> list[str]
```

רשימת כל הסודות הזמינים (שמות בלבד).

**Returns:** `list[str]` - רשימת שמות הסודות

---

#### verify_access

```python
def verify_access(self, secret_id: str) -> bool
```

אימות גישה לסוד בלי לטעון את הערך.

**Parameters:**

| פרמטר | טיפוס | תיאור |
|-------|-------|-------|
| `secret_id` | `str` | שם הסוד לאימות |

**Returns:** `bool` - True אם הסוד נגיש

---

#### load_secrets_to_env

```python
def load_secrets_to_env(self, secret_mapping: dict[str, str]) -> int
```

טעינת סודות למשתני סביבה.

**Parameters:**

| פרמטר | טיפוס | תיאור |
|-------|-------|-------|
| `secret_mapping` | `dict[str, str]` | מיפוי שם משתנה → שם סוד |

**Returns:** `int` - מספר הסודות שנטענו בהצלחה

**Example:**

```python
manager.load_secrets_to_env({
    "DATABASE_URL": "db-connection-string",
    "API_KEY": "external-api-key"
})
```

---

#### clear_cache

```python
def clear_cache(self) -> None
```

ניקוי ה-cache של הסודות.

!!! tip "טיפ"
    קרא לפונקציה זו אחרי שימוש בסודות לשחרור זיכרון.

---

## Convenience Function

### get_secret

```python
from src.secrets_manager import get_secret

secret = get_secret(secret_id: str, project_id: str | None = None) -> str | None
```

פונקציית נוחות לשליפת סוד יחיד.

**Example:**

```python
from src.secrets_manager import get_secret

api_key = get_secret("ANTHROPIC-API")
```
