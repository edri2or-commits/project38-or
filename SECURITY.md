# Security Policy

## 🔒 אבטחת סודות

פרויקט זה מיישם גישה אוטונומית ל-GCP Secret Manager עם אבטחה מרבית.

### עקרונות אבטחה

1. **אף פעם לא לשמור סודות בקוד**
   - כל הסודות מאוחסנים ב-GCP Secret Manager
   - אף סוד לא נמצא בקבצי קוד או בגיט

2. **אף פעם לא להדפיס סודות**
   - המערכת מונעת חשיפת סודות בלוגים
   - כל השגיאות מוסתרות ללא פרטים רגישים

3. **שימוש ב-Service Account**
   - כל הגישה ל-secrets עוברת דרך service account מורשה
   - Service Account: `claude-code-agent@project38-483612.iam.gserviceaccount.com`

4. **הרשאות מינימליות**
   - Service account מקבל רק הרשאות נדרשות
   - `secretmanager.secretAccessor` - קריאה בלבד
   - `secretmanager.viewer` - רשימת secrets (אופציונלי)

### ⚠️ אל תעשה את זה

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

### ✅ עשה את זה

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

### 🔐 GitHub Secrets

הסיקרט `GCP_SERVICE_ACCOUNT_KEY` מאוחסן בצורה מאובטחת ב-GitHub:
- מוצפן על ידי GitHub
- נגיש רק ל-workflows בריפו זה
- לעולם לא נחשף בלוגים

### 📝 דיווח על בעיות אבטחה

אם מצאת בעיית אבטחה:
1. **אל תפתח issue ציבורי**
2. פנה ישירות לבעלי הפרויקט
3. תאר את הבעיה בפרטי פרטים
4. אנו נטפל בבעיה בדחיפות

### 🔄 עדכוני אבטחה

- עדכן את `google-cloud-secret-manager` באופן קבוע
- בדוק הרשאות Service Account תקופתית
- סרוק קוד לאיתור סודות עם `git-secrets` או כלים דומים

### 📚 מקורות נוספים

- [GCP Secret Manager Best Practices](https://cloud.google.com/secret-manager/docs/best-practices)
- [GitHub Secrets Security](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
