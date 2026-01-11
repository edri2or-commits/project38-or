# GitHub Pull Request Operations

## סקירה מהירה

מודול אוניברסלי ליצירת Pull Requests שעובד בכל סביבה, עם או בלי gh CLI.

```python
from src.github_pr import create_pr

pr = create_pr(
    title="Add feature X",
    body="## Summary\nAdds feature X",
    repo="owner/repo",
    head="feature/x"
)

if pr:
    print(f"Created PR #{pr['number']}: {pr['url']}")
```

!!! info "פתרון אוניברסלי"
    מודול זה פותר את בעיית זמינות gh CLI על ידי fallback אוטומטי ל-requests library.

---

## Functions

### create_pr

::: src.github_pr.create_pr
    options:
      show_root_heading: true
      heading_level: 3

### create_pr_with_gh

::: src.github_pr.create_pr_with_gh
    options:
      show_root_heading: true
      heading_level: 3

### create_pr_with_requests

::: src.github_pr.create_pr_with_requests
    options:
      show_root_heading: true
      heading_level: 3

### ensure_gh_cli

::: src.github_pr.ensure_gh_cli
    options:
      show_root_heading: true
      heading_level: 3

---

## דוגמאות שימוש

### יצירת PR בסיסית

```python
from src.github_pr import create_pr

pr = create_pr(
    title="feat: add new feature",
    body="## Summary\n\nAdds new feature X",
    repo="owner/repo",
    head="feature/new-feature"
)

if pr:
    print(f"✅ PR #{pr['number']}: {pr['url']}")
else:
    print("❌ Failed to create PR")
```

### יצירת PR עם branch detection אוטומטי

```python
from src.github_pr import create_pr

# head=None יגרום לזיהוי אוטומטי של ה-branch הנוכחי
pr = create_pr(
    title="fix: bug fix",
    body="Fixes bug in module X",
    repo="owner/repo"
)
```

### בדיקת זמינות gh CLI

```python
from src.github_pr import ensure_gh_cli

if ensure_gh_cli():
    print("✅ gh CLI available")
else:
    print("⚠️  gh CLI not available (will use requests fallback)")
```

### שימוש ב-Skills

```python
# בתוך skill, השתמש תמיד ב-create_pr
from src.github_pr import create_pr

# זה יעבוד גם אם gh לא מותקן
pr = create_pr(
    title="docs: update documentation",
    body=pr_body_text,
    repo="owner/repo",
    head="docs/update"
)
```

---

## איך זה עובד

### שיטת Fallback

1. **מנסה gh CLI** אם זמין:
   ```bash
   gh pr create --title "..." --body "..." --repo owner/repo
   ```

2. **נופל ל-requests** אם gh לא זמין:
   ```python
   requests.post(
       "https://api.github.com/repos/owner/repo/pulls",
       headers={"Authorization": f"token {token}"},
       json={"title": "...", "body": "...", "head": "...", "base": "main"}
   )
   ```

### זיהוי Token

מחפש token לפי סדר עדיפות:

1. `GH_TOKEN` environment variable
2. `GITHUB_TOKEN` environment variable
3. `gh auth token` command output

### זיהוי Branch אוטומטי

אם `head` לא סופק:

```bash
git rev-parse --abbrev-ref HEAD
```

---

## אבטחה

!!! warning "אזהרת אבטחה"
    - **לעולם אל תדפיס או תרשום tokens**
    - המודול לעולם לא מדפיס ערכי tokens
    - כל הטיפול ב-tokens נעשה בזיכרון בלבד

### דוגמאות טובות/רעות

```python
# ❌ WRONG - exposes token
token = get_token()
print(f"Using token: {token}")

# ✅ RIGHT - use without exposing
pr = create_pr(
    title="...",
    body="...",
    repo="owner/repo"
)
# Token used internally, never printed
```

---

## פתרון בעיות

### gh CLI לא זמין

**תסמין:**
```
gh: command not found
```

**פתרון:**
המודול אוטומטית נופל ל-requests library. אין צורך בפעולה.

### 401 Unauthorized עם requests

**תסמין:**
```python
pr = create_pr(...)
# Returns None
```

**אפשרויות:**
1. Token לא זמין ב-environment
2. Token פג תוקף
3. Token חסר הרשאות

**פתרון:**
```bash
# בדוק token
echo "GH_TOKEN: ${GH_TOKEN:+SET}"

# אם חסר, הגדר:
export GH_TOKEN="github_pat_..."

# או השתמש ב-gh auth:
gh auth login
```

### Merge conflicts ב-PR

**ראה:** `CLAUDE.md:673-810` - Troubleshooting: Git Push & Merge Conflicts

---

## השוואה: gh CLI vs requests

| Feature | gh CLI | requests |
|---------|--------|----------|
| **מהירות** | מהיר יותר | מהיר |
| **זמינות** | לא מובטח | תמיד זמין (built-in) |
| **Proxy handling** | מצוין | טוב |
| **Setup** | דורש התקנה | אין צורך |
| **Authentication** | gh auth או GH_TOKEN | GH_TOKEN בלבד |

---

## קישורים

- [GitHub API: Pull Requests](https://docs.github.com/en/rest/pulls/pulls)
- [gh CLI Documentation](https://cli.github.com/manual/gh_pr_create)
- [CLAUDE.md:634-669](../../CLAUDE.md) - GitHub PR Operations section
- [CLAUDE.md:673-810](../../CLAUDE.md) - Troubleshooting guide
