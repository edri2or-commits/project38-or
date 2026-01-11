# GitHub App Authentication

## סקירה מהירה

מודול לאימות GitHub App וייצור Installation Access Tokens.

```python
from src.github_auth import get_installation_token, configure_gh_cli

# קבלת token
token = get_installation_token()

# קונפיגורציה אוטומטית של gh CLI
if configure_gh_cli():
    # gh commands will now work
    pass
```

!!! info "שימוש"
    המודול משתמש ב-GCP Secret Manager לשליפת המפתח הפרטי (`github-app-private-key`).

---

## Functions

### generate_jwt

::: src.github_auth.generate_jwt
    options:
      show_root_heading: true
      heading_level: 3

### get_installation_token

::: src.github_auth.get_installation_token
    options:
      show_root_heading: true
      heading_level: 3

### configure_gh_cli

::: src.github_auth.configure_gh_cli
    options:
      show_root_heading: true
      heading_level: 3

---

## Constants

### GITHUB_APP_ID

```python
GITHUB_APP_ID = 2497877
```

מזהה ה-GitHub App של הפרויקט.

### GITHUB_INSTALLATION_ID

```python
GITHUB_INSTALLATION_ID = 100231961
```

מזהה ההתקנה (installation) של האפליקציה ברפוזיטורי/ארגון.

---

## דוגמאות שימוש

### קבלת Installation Token

```python
from src.github_auth import get_installation_token

token = get_installation_token()
if token:
    print("✅ Token received (valid for 1 hour)")
    # Use token for GitHub API calls
else:
    print("❌ Failed to get token")
```

### קונפיגורציה של gh CLI

```python
from src.github_auth import configure_gh_cli

if configure_gh_cli():
    print("✅ gh CLI configured")
    # Now gh commands will use the installation token
    import subprocess
    result = subprocess.run(["gh", "repo", "view"], capture_output=True)
else:
    print("❌ Configuration failed")
```

### שימוש מלא עם Secret Manager

```python
from src.secrets_manager import SecretManager
from src.github_auth import generate_jwt

# הצג שהמפתח נגיש (אל תדפיס אותו!)
manager = SecretManager()
if manager.verify_access("github-app-private-key"):
    print("✅ Private key accessible")

# קבל token
from src.github_auth import get_installation_token
token = get_installation_token()

# השתמש ב-token (אל תדפיס אותו!)
# Example: GitHub API call
```

---

## אבטחה

!!! warning "אזהרת אבטחה"
    - **לעולם אל תדפיס או תרשום tokens או private keys**
    - Tokens תקפים ל-1 שעה
    - JWT תקף ל-10 דקות
    - השתמש ב-`SecretManager` לשליפת המפתח הפרטי

### טיפול בטוקנים

```python
# ❌ WRONG - exposes token
print(f"Token: {token}")
logger.info(f"Got token: {token}")

# ✅ RIGHT - use without exposing
import os
os.environ["GH_TOKEN"] = token
# Or pass directly to API client
```

---

## זרימת אימות

```
1. SecretManager.get_secret("github-app-private-key")
   ↓
2. generate_jwt(app_id, private_key)
   ↓ JWT valid for 10 minutes
3. POST /app/installations/{id}/access_tokens
   ↓
4. Installation Token (valid for 1 hour)
   ↓
5. Use token for GitHub API calls
```

---

## שגיאות נפוצות

### Token Generation Failed

```python
token = get_installation_token()
if token is None:
    # Possible reasons:
    # 1. Private key not accessible in Secret Manager
    # 2. JWT generation failed
    # 3. GitHub API request failed
    # 4. Network timeout
    pass
```

### gh CLI Configuration Failed

```python
if not configure_gh_cli():
    # Possible reasons:
    # 1. Token generation failed
    # 2. gh CLI not installed
    # 3. gh auth status check failed
    pass
```

---

## קישורים

- [GitHub Apps Documentation](https://docs.github.com/en/apps)
- [JWT Authentication](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app)
- [Installation Access Tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app)
