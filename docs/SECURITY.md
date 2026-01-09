# Security Policy

## 🔒 אבטחת סודות

פרויקט זה מיישם גישה אוטונומית ל-GCP Secret Manager עם אבטחה מרבית.

---

## 🛡️ Workflow Hardening (2026-01-09)

### שינויים שבוצעו

בעקבות ביקורת אבטחה, בוצעו השינויים הבאים בכל 4 ה-workflows:

#### 1. הסרת Push Triggers
**לפני:** Workflows הופעלו על `push` ל-`main` או `claude/**`
**אחרי:** רק `workflow_dispatch` (הרצה ידנית)

**סיבה:** ב-public repo, push triggers יכולים להיות מנוצלים לרעה. הגבלה ל-workflow_dispatch מבטיחה שרק בעלי הרשאות מתאימות יכולים להפעיל workflows שניגשים ל-GCP credentials.

#### 2. הוספת Permissions מינימליים
**לפני:** אין הגדרת `permissions` - default רחב מדי
**אחרי:** כל workflow מגדיר `permissions` מפורשות

```yaml
# רוב ה-workflows - קריאה בלבד
permissions:
  contents: read

# report-secrets.yml - צריך לכתוב דוח
permissions:
  contents: write
```

**סיבה:** Principle of least privilege - כל workflow מקבל רק את ההרשאות הנדרשות לו.

#### 3. הוספת Concurrency Control
**לפני:** אין הגבלה על ריצות מקבילות
**אחרי:** כל workflow כולל:

```yaml
concurrency:
  group: <workflow-name>-${{ github.ref }}
  cancel-in-progress: true
```

**סיבה:** מניעת race conditions והבטחת שרק ריצה אחת פעילה בכל רגע.

### Workflows מעודכנים

| Workflow | Trigger | Permissions | Concurrency |
|----------|---------|-------------|-------------|
| verify-secrets.yml | workflow_dispatch | contents: read | ✅ |
| quick-check.yml | workflow_dispatch | contents: read | ✅ |
| report-secrets.yml | workflow_dispatch | contents: write | ✅ |
| gcp-secret-manager.yml | workflow_dispatch | contents: read | ✅ |

---

## עקרונות אבטחה

### 1. אף פעם לא לשמור סודות בקוד
- כל הסודות מאוחסנים ב-GCP Secret Manager
- אף סוד לא נמצא בקבצי קוד או בגיט

### 2. אף פעם לא להדפיס סודות
- המערכת מונעת חשיפת סודות בלוגים
- כל השגיאות מוסתרות ללא פרטים רגישים
- **אומת בביקורת:** אף workflow לא מדפיס ערכי סודות - רק שמות וגדלים

### 3. שימוש ב-Service Account
- כל הגישה ל-secrets עוברת דרך service account מורשה
- Service Account: `claude-code-agent@project38-483612.iam.gserviceaccount.com`

### 4. הרשאות מינימליות
- Service account מקבל רק הרשאות נדרשות
- `secretmanager.secretAccessor` - קריאה בלבד
- `secretmanager.viewer` - רשימת secrets (אופציונלי)

---

## ⚠️ אל תעשה את זה

❌ **לעולם אל תעשה:**
```python
# רע - מדפיס סוד!
secret = manager.get_secret("api-key")
print(f"API Key: {secret}")

# רע - שומר סוד בקובץ!
with open("secret.txt", "w") as f:
    f.write(secret)

# רע - שולח סוד ללוג!
logger.info(f"Using API key: {secret}")

# רע - מחזיר סוד ב-API response!
return {"api_key": secret}
```

## ✅ עשה את זה

✅ **שימוש נכון:**
```python
# טוב - שומר סוד בזיכרון בלבד
secret = manager.get_secret("api-key")
if secret:
    client = APIClient(api_key=secret)
    # השתמש בסוד, אל תדפיס אותו!

# טוב - טען למשתני סביבה
manager.load_secrets_to_env({"API_KEY": "api-key"})
client = APIClient(api_key=os.environ["API_KEY"])

# טוב - נקה אחרי שימוש
del secret
manager.clear_cache()
```

---

## 🔐 GitHub Secrets

הסיקרט `GCP_SERVICE_ACCOUNT_KEY` מאוחסן בצורה מאובטחת ב-GitHub:
- מוצפן על ידי GitHub
- נגיש רק ל-workflows בריפו זה
- לעולם לא נחשף בלוגים

---

## 📝 דיווח על בעיות אבטחה

אם מצאת בעיית אבטחה:
1. **אל תפתח issue ציבורי**
2. פנה ישירות לבעלי הפרויקט
3. תאר את הבעיה בפרטי פרטים
4. אנו נטפל בבעיה בדחיפות

---

## 🔄 עדכוני אבטחה

- עדכן את `google-cloud-secret-manager` באופן קבוע
- בדוק הרשאות Service Account תקופתית
- סרוק קוד לאיתור סודות עם `git-secrets` או כלים דומים

---

## 📚 מקורות נוספים

- [GCP Secret Manager Best Practices](https://cloud.google.com/secret-manager/docs/best-practices)
- [GitHub Secrets Security](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [GitHub Actions Security Hardening](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
