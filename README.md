# project38-or

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