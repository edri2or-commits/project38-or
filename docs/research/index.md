# מסמכי מחקר

סיכומי מחקר שמנחים את החלטות הארכיטקטורה של הפרויקט.

## רשימת מסמכים

| # | נושא | תקציר |
|---|------|-------|
| 01 | [תשתית תיעוד](01_documentation_infrastructure_zero_tolerance.summary.md) | MkDocs + Material, Docs-as-Code |
| 02 | [SQLModel vs SQLAlchemy](02_sqlmodel_vs_sqlalchemy_async_persistence.summary.md) | בחירת ORM לפרויקט |
| 03 | [Claude Code Architecture](03_claude_code_architecture_technical_guide.summary.md) | ארכיטקטורת CLI והרחבות |
| 04 | [Agent Layer](04_autonomous_agent_layer_architecture.summary.md) | שכבת סוכנים אוטונומיים |
| 05 | [Agentic Fortress](05_agentic_fortress_security_architecture.summary.md) | אבטחה לסוכנים |
| 06 | [Documentation Agents](06_autonomous_documentation_agents.summary.md) | סוכני תיעוד אוטומטיים |
| 07 | [Claude Skills](07_claude_skills_enterprise_implementation.summary.md) | מימוש Skills ארגוני |

## החלטות ארכיטקטורה מרכזיות

מבוסס על המחקר:

| החלטה | נימוק | מקור |
|--------|-------|------|
| MkDocs + Material | התאמה ל-FastAPI ecosystem | Research 01 |
| SQLModel + asyncpg | אינטגרציה עם Pydantic | Research 02 |
| Hooks לשליטה ב-agent | שערי אבטחה דטרמיניסטיים | Research 03 |
| PostgreSQL כ-backbone | פשטות על פני Redis/RabbitMQ | Research 04 |
| WIF על פני static keys | credentials חולפים | Research 05 |
| GitHub App לאוטומציה | rate limits גבוהים, audit trail | Research 06 |
| Skills לסטנדרטיזציה | התנהגויות agent מנוהלות בגרסאות | Research 07 |
