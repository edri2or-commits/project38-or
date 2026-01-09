# project38-or

## 🚀 סקירה מהירה

מערכת לגישה אוטונומית ל-GCP Secret Manager עם אבטחה מלאה.
הסודות נטענים באופן אוטומטי **בלי לחשוף אותם** בלוגים או בקוד.

### ✨ יכולות

- ✅ גישה אוטונומית לסודות מ-Secret Manager
- 🔒 אבטחה מלאה - סודות לעולם לא נחשפים
- 🐍 Python module מוכן לשימוש
- 🔄 GitHub Actions workflows אוטומטיים
- 📦 ניהול cache וזיכרון בטוח

### 📦 מבנה הפרויקט

```
project38-or/
├── src/
│   ├── __init__.py
│   └── secrets_manager.py      # מודול ראשי לניהול סודות
├── .github/workflows/
│   ├── gcp-secret-manager.yml  # דוגמת workflow
│   └── verify-secrets.yml      # אימות גישה לסודות
├── example_usage.py             # דוגמאות שימוש
├── requirements.txt             # תלויות Python
└── README.md
```

### 🎯 שימוש מהיר

```python
from src.secrets_manager import SecretManager

manager = SecretManager()

# קבל סוד (בלי לחשוף!)
secret = manager.get_secret("my-secret-name")

# רשימת כל הסודות הזמינים
secrets = manager.list_secrets()

# טען סודות למשתני סביבה
manager.load_secrets_to_env({
    "DATABASE_URL": "db-connection",
    "API_KEY": "api-key-secret"
})
```

## 🔐 GCP Secret Manager Access

הפרויקט מוגדר עם גישה ל-GCP Secret Manager באמצעות Service Account.

### פרטי ה-Service Account

- **📝 Service Account**: `claude-code-agent@project38-483612.iam.gserviceaccount.com`
- **🆔 Project ID**: `project38-483612`
- **🔐 GitHub Secret**: `GCP_SERVICE_ACCOUNT_KEY`

### שימוש ב-GitHub Actions

#### דרך 1: שימוש ב-google-github-actions/auth

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Authenticate to GCP
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SERVICE_ACCOUNT_KEY }}

      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v2

      - name: Access Secret from Secret Manager
        run: |
          SECRET_VALUE=$(gcloud secrets versions access latest --secret="YOUR_SECRET_NAME")
          echo "Secret accessed successfully"
```

#### דרך 2: הגדרה ידנית של credentials

```yaml
steps:
  - name: Setup GCP credentials
    run: |
      echo '${{ secrets.GCP_SERVICE_ACCOUNT_KEY }}' > /tmp/gcp-key.json
      export GOOGLE_APPLICATION_CREDENTIALS=/tmp/gcp-key.json

  - name: Install gcloud
    uses: google-github-actions/setup-gcloud@v2

  - name: Authenticate with service account
    run: |
      gcloud auth activate-service-account --key-file=/tmp/gcp-key.json
```

### שימוש בקוד (Python)

```python
from google.cloud import secretmanager

def access_secret(project_id, secret_id, version_id="latest"):
    """Access a secret from Secret Manager"""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"

    response = client.access_secret_version(request={"name": name})
    payload = response.payload.data.decode("UTF-8")
    return payload

# שימוש
project_id = "project38-483612"
secret_value = access_secret(project_id, "my-secret-name")
```

### יצירת סיקרט חדש ב-Secret Manager

```bash
# דרך gcloud CLI
echo -n "my-secret-value" | gcloud secrets create my-secret-name \
    --data-file=- \
    --project=project38-483612

# הענקת הרשאות ל-service account
gcloud secrets add-iam-policy-binding my-secret-name \
    --member="serviceAccount:claude-code-agent@project38-483612.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --project=project38-483612
```

### Workflow לדוגמה

ניתן להריץ את ה-workflow לדוגמה:
```bash
# ב-GitHub UI: Actions → GCP Secret Manager Access → Run workflow
# או push ל-main/claude/** branches
```

הקובץ `.github/workflows/gcp-secret-manager.yml` מכיל דוגמה מלאה לשימוש ב-Secret Manager.

### הרשאות נדרשות

ודא ש-service account יש את ההרשאות הבאות:
- `roles/secretmanager.secretAccessor` - לקריאת secrets
- `roles/secretmanager.viewer` - לרשימת secrets (אופציונלי)

---

## 🛠️ שימוש במערכת

### התקנה מקומית

```bash
# התקן תלויות
pip install -r requirements.txt

# הרץ דוגמאות
python example_usage.py

# הרץ את המודול ישירות (יציג רשימת סודות)
python src/secrets_manager.py
```

### שימוש ב-GitHub Actions

המערכת כוללת 2 workflows אוטומטיים:

1. **Verify Secret Access** - מאמת גישה לסודות (בלי לחשוף!)
   ```bash
   # הרץ דרך GitHub UI: Actions → Verify Secret Access → Run workflow
   ```

2. **GCP Secret Manager Access** - דוגמה מלאה לשימוש
   ```bash
   # הרץ דרך GitHub UI: Actions → GCP Secret Manager Access → Run workflow
   ```

שני ה-workflows מתבצעים אוטומטית גם ב-push ל-`main` או `claude/**` branches.

### שימוש בקוד שלך

```python
# דרך 1: שימוש בסיסי
from src.secrets_manager import get_secret

api_key = get_secret("my-api-key")
if api_key:
    # השתמש בסוד...
    pass

# דרך 2: שימוש מתקדם
from src.secrets_manager import SecretManager

manager = SecretManager()

# בדוק אילו סודות קיימים
available = manager.list_secrets()
print(f"Available: {available}")

# טען סודות למשתני סביבה
manager.load_secrets_to_env({
    "DB_URL": "database-url",
    "API_KEY": "api-key"
})

import os
db_url = os.environ.get("DB_URL")  # עכשיו זמין!
```

### דוגמת שימוש ב-Workflow

```yaml
- name: Use secrets in your application
  run: |
    python << 'EOF'
    from src.secrets_manager import SecretManager

    manager = SecretManager()

    # טען סודות
    manager.load_secrets_to_env({
        "DATABASE_URL": "prod-db-url",
        "API_KEY": "external-api-key"
    })

    # הרץ את האפליקציה שלך
    # היא תוכל לגשת לסודות דרך os.environ
    EOF
```

## 🔒 עקרונות אבטחה

1. **אף פעם לא להדפיס סודות** - המודול מוודא שסודות לא נחשפים בלוגים
2. **Cache בזיכרון** - סודות נשמרים רק בזיכרון, לא בקבצים
3. **ניקוי אוטומטי** - ניתן לנקות cache עם `manager.clear_cache()`
4. **טיפול בשגיאות** - המערכת מטפלת בחסרי הרשאות וסודות לא קיימים
5. **אימות גישה** - `verify_access()` בודק גישה בלי לטעון את הערך

## 📝 צעדים הבאים

עכשיו שיש לך גישה אוטונומית לסודות, תוכל:

1. 🏗️ **לבנות אפליקציה** שמשתמשת בסודות
2. 🚀 **להגדיר CI/CD** עם גישה לסודות
3. 🔄 **לשלב בתהליכי deployment**
4. 📊 **להוסיף monitoring ו-logging** (בלי לחשוף סודות!)
5. 🧪 **לבנות tests** שמשתמשים בסודות

המערכת מוכנה לשימוש ומאובטחת! 🎉