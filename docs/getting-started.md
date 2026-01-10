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

## Documentation Updater (Autonomous Skill)

המערכת כוללת skill אוטונומי לעדכון תיעוד אוטומטי.

### שימוש ב-Doc Updater

```python
from src.doc_updater import ChangelogManager, DocstringChecker

# עדכון changelog
manager = ChangelogManager("docs/changelog.md")
manager.add_entry("Added", "New feature description")
manager.add_entry("Fixed", "Bug fix description")
manager.write()

# בדיקת docstrings
checker = DocstringChecker("src")
success, output = checker.check()
if not success:
    print(f"Docstring errors: {output}")
```

### הפעלת Skill (Claude Code)

```bash
# בסביבת Claude Code CLI
/doc-updater
```

### שימוש דרך CLI

```bash
# בדוק אם התיעוד מעודכן
python3 src/doc_updater.py --check

# אמת docstrings וסרוק סודות
python3 src/doc_updater.py --verify

# קבל הצעות לעדכון changelog
python3 src/doc_updater.py --suggest

# הצג מידע כללי (ברירת מחדל)
python3 src/doc_updater.py
```

**Exit Codes:**
- `0` - הכל תקין
- `1` - נדרשת תשומת לב (changelog חסר, docstrings שגויים, וכו')

### Automation אוטומטית

ה-skill רץ באופן אוטומטי:
- ✅ **GitHub Actions** - בכל PR שמשנה קבצי `src/`
- ✅ **Manual Trigger** - דרך workflow_dispatch
- ✅ **Pre-commit Hook** - בדיקה מקומית לפני כל commit

**התקנת Pre-commit Hook:**
```bash
# התקנה מהירה
bash .hooks/install.sh

# בדיקה ידנית
bash .hooks/pre-commit

# הסרה
rm .git/hooks/pre-commit
```

**מה ה-hook בודק:**
- Docstrings תקינים (Google style)
- אין סודות חשופים בקבצים staged
- תזכורת לעדכן changelog כשיש שינויים ב-src/

**לעקוף את ה-hook (לא מומלץ):**
```bash
git commit --no-verify
```

ה-skill יבצע באופן אוטומטי:
1. **זיהוי שינויים** - מזהה קבצי Python שהשתנו ב-src/
2. **עדכון changelog** - מוסיף ערכים ל-docs/changelog.md
3. **בדיקת docstrings** - מריץ pydocstyle לוידוא Google-style docstrings
4. **יצירת API docs** - מעדכן docs/api/ באופן אוטומטי

### מה הכלים בודקים

**DocstringChecker**:
- כל פונקציה ציבורית חייבת docstring
- פורמט Google style נדרש
- טיפול בשגיאות מתועד

**Secret Detection**:
- סריקת תוכן למניעת חשיפת סודות
- תבניות: API keys, tokens, passwords
- חסימה אוטומטית של תיעוד עם סודות

### דוגמה מלאה

```python
from src.doc_updater import (
    ChangelogManager,
    DocstringChecker,
    get_changed_python_files,
    detect_secrets_in_content
)

# 1. מצא קבצים שהשתנו
changed_files = get_changed_python_files()
print(f"Changed: {changed_files}")

# 2. בדוק docstrings
for file_path in changed_files:
    checker = DocstringChecker()
    success, output = checker.check(file_path)
    if not success:
        print(f"⚠️  {file_path}: {output}")

# 3. עדכן changelog
manager = ChangelogManager()
manager.add_entry("Changed", f"Updated {len(changed_files)} modules")
updated_content = manager.write(dry_run=True)

# 4. בדוק שאין סודות
secrets = detect_secrets_in_content(updated_content)
if secrets:
    print(f"❌ Secrets detected: {secrets}")
else:
    # בטוח לכתוב
    manager.write()
```

## הצעד הבא

- קרא את [מדיניות האבטחה](SECURITY.md)
- הבן את [תוכנית הארכיטקטורה](BOOTSTRAP_PLAN.md)
- עיין ב[מסמכי המחקר](research/index.md)
- למד על [Doc-Updater Skill](.claude/skills/doc-updater/SKILL.md)
