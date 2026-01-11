# דו"ח מחקר ויישום מקיף: רתמת סוכן רציפה (Long-Running Agent Harness)

## תקציר מנהלים

בעידן הנוכחי של הנדסת תוכנה מבוססת בינה מלאכותית (AI Software Engineering), אנו עדים למעבר פרדיגמטי משמעותי: ממודל של "סייענים" (Copilots) המגיבים לפקודות נקודתיות, למודל של "סוכנים אוטונומיים" (Autonomous Agents) המסוגלים לנהל ולבצע משימות מורכבות לאורך פרקי זמן ארוכים. האתגר הטכנולוגי המרכזי המעכב מעבר זה אינו יכולת ההסקה (Reasoning) של המודלים, אלא מגבלת "חלון ההקשר" (Context Window) והניהול האפקטיבי של זיכרון המערכת לאורך זמן.

מסמך מחקר ויישום זה מציג תוכנית מקיפה, מפורטת ומעשית לבניית "רתמת סוכן" (Agent Harness) – ארכיטקטורת שליטה ובקרה המבוססת על עקרונות המחקר של חברת Anthropic והדגמות טכניות של המהנדס Cole Medin. הרתמה המוצעת פותרת את בעיית "רווית ההקשר" (Context Saturation) באמצעות יישום לולאת עבודה רקורסיבית (Execute-Summarize-Reset), המאפשרת לסוכן ה-AI לפעול באופן רציף, לנהל משימות בפלטפורמות חיצוניות כגון Linear, ולבצע שינויי קוד מאובטחים בסביבת Docker מבודדת.

הדו"ח מפרק את המערכת לרכיבים ארכיטקטוניים בדידים, מספק אסטרטגיית אינטגרציה עם פרוטוקול ההקשר של המודל (MCP), ומציע תוכנית בניה ארבע-שלבית (Four-Phase Build Plan) המוכנה ליישום מיידי. הדגש מושם על יצירת מערכת "היברידית" המשלבת את הגמישות הקוגניטיבית של מודל Claude 3.5 Sonnet עם הקשיחות והאמינות של קוד Python דטרמיניסטי לניהול המצב (State Management).

## 1. מבוא: האבולוציה של סוכני פיתוח והאתגר הקונטקסטואלי

### 1.1 המעבר מאינטראקציה לאוטונומיה

עד לאחרונה, השימוש במודלי שפה גדולים (LLMs) לפיתוח תוכנה התאפיין באינטראקציות קצרות טווח. המפתח האנושי סיפק הקשר (Context), המודל הציע קטע קוד (Snippet), והאדם ביצע את האינטגרציה. תהליך זה, המכונה "Human-in-the-loop", יעיל למשימות נקודתיות אך נכשל בניהול פרויקטים מערכתיים. המעבר ל-"Agentic Workflow" דורש מהמערכת לא רק לכתוב קוד, אלא גם לתכנן (Plan), לבדוק (Test), ולתקן (Debug) את עצמה ללא התערבות אדם.

המחקר של Anthropic, כפי שמוצג במאמר "Effective Harness for Long-Running Agents", מזהה כי המכשול העיקרי אינו אינטליגנציה אלא "סיבולת קוגניטיבית". ככל שהסשן מתארך, המודל נחשף ליותר רעש (לוגים של שגיאות, ניסיונות כושלים, קבצים לא רלוונטיים), מה שמוביל לירידה דרמטית בביצועים (Performance Degradation) ולתופעת ה-"Lost in the Middle", בה המודל שוכח הנחיות ראשוניות קריטיות.

### 1.2 בעיית רווית ההקשר (Context Saturation Problem)

גם עם חלונות הקשר רחבים של 200,000 טוקנים (כפי שקיים ב-Claude 3.5 Sonnet), פרויקט תוכנה ממוצע ממלא את החלון במהירות. קריאת קבצי קוד, הרצת בדיקות, וקבלת פלט מהטרמינל מייצרים עומס טוקנים עצום. כאשר החלון מתמלא:

- **עלויות מרקיעות שחקים**: כל קריאה ל-API מחייבת עיבוד מחדש של כל ההיסטוריה.
- **ירידה במיקוד**: המודל מתקשה להבחין בין ההוראה המקורית ("בנה משחק Snake") לבין פרטי המימוש הטכניים האחרונים שראה.
- **הזיות (Hallucinations)**: הסבירות להמצאת פונקציות שאינן קיימות עולה ככל שהזיכרון "מזוהם".

הפתרון אינו הגדלת החלון לנצח, אלא ניהול חכם של "זיכרון עבודה" (Working Memory) מול "זיכרון לטווח ארוך" (Long-Term Memory). הרתמה (Harness) משמשת כהיפוקמפוס מלאכותי, המעביר מידע מהזיכרון הקצר (Context Window) לזיכרון הארוך (קבצים, Linear, Git) ומנקה את הלוח לקראת המשימה הבאה.

## 2. פרוטוקול Anthropic: מפרט טכני ועקרונות ליבה

הפרוטוקול של Anthropic מציע ארכיטקטורה מפוצלת לניהול מחזור חיי הסוכן. המהות של הפרוטוקול היא ההכרה בכך שמשימה ארוכה מורכבת מרצף של משימות קצרות, המופרדות על ידי נקודות סנכרון (Checkpoints).

### 2.1 ארכיטקטורת הסוכן הכפול (The Dual-Agent Pattern)

הפרוטוקול מגדיר שתי ישויות נפרדות הפועלות בשלבים שונים של הפרויקט:

#### א. סוכן האתחול (The Initializer Agent)
זהו ה"ארכיטקט" של המערכת. הוא רץ פעם אחת בלבד בתחילת הפרויקט (Day 0).

- **קלט**: מסמך דרישות ברמה גבוהה (High-Level App Spec / PRD).
- **תפקיד**: לנתח את הדרישות, להקים את תשתית הפרויקט (Scaffolding), ולהגדיר את תוכנית העבודה.
- **פלט קריטי**: יצירת רשימת משימות (Task List) במערכת ניהול חיצונית (Linear/Jira) ויצירת קובץ הקשר ראשוני.

#### ב. סוכן העבודה/הקידוד (The Worker/Coding Agent)
זהו ה"מפתח" (Developer). הוא פועל בלולאה אינסופית (Loop).

- **קלט**: המשימה הבאה בתור (Next Ticket), מצב הקוד הנוכחי (Git State), וארטיפקט המסירה (Handoff Artifact).
- **תפקיד**: לקחת משימה בודדת, לממש אותה, לבדוק אותה, ולעדכן את הסטטוס.
- **אילוץ**: הסוכן חייב להניח שהוא "מתעורר" בכל פעם מחדש ללא זיכרון מהסשן הקודם, למעט מה שמופיע בארטיפקטים החיצוניים.

### 2.2 מפרט ארטיפקט המסירה (The Handoff Artifact Specification)

המפתח להצלחת הרתמה הוא איכות ה-Handoff. זהו המנגנון המגשר על "השכחה" המכוונת בין הסשנים. המחקר מראה כי ארטיפקט זה חייב להיות מובנה (Structured) ולא טקסט חופשי אסוציאטיבי.

#### מבנה נתונים מומלץ (Markdown/XML):

על בסיס הניתוח של הוידאו והמאמר, המבנה האופטימלי כולל:

| שדה | תיאור | חשיבות |
|------|--------|---------|
| Current Objective | המטרה הנוכחית ברמה הגבוהה | מונע "סחיפה" (Drift) מהיעד המקורי |
| Completed Steps | רשימת הפעולות שבוצעו בהצלחה בסשן האחרון | מונע חזרה מיותרת על עבודה שכבר נעשתה |
| Active Context | נתיבי קבצים רלוונטיים ומשתני סביבה קריטיים | חוסך לסוכן הבא זמן חיפוש |
| Known Issues | באגים פתוחים או בדיקות שנכשלו | מאפשר לסוכן הבא להתמקד בתיקון מיידי |
| Next Immediate Action | הפקודה המדויקת הבאה שיש להריץ | Prompt מפורש לסוכן העתידי |

#### דוגמה לייצוג טכני של הארטיפקט:

```markdown
# Handoff Artifact

## Status
- Current Phase: Authentication System Implementation
- Last Action: Implemented JWT middleware in src/auth/middleware.py
- Outcome: Unit tests passed, but integration test test_login_flow failed

## Context
- Modified Files: src/auth/middleware.py, src/routes/users.py
- New Dependencies: pyjwt, passlib added to requirements.txt

## Next Steps
- Debug test_login_flow - likely an issue with the token expiration time setting
- Once fixed, commit changes and move Linear ticket LIN-142 to "Done"
```

## 3. ארכיטקטורת המערכת וניהול המצב

כדי לממש את הפרוטוקול, אנו נדרשים לבנות מערכת "תזמור" (Orchestrator) חיצונית למודל ה-LLM. מערכת זו, הכתובה ב-Python, מנהלת את לוגיקת המעבר בין המצבים (State Machine).

### 3.1 תרשים ארכיטקטורה (טקסטואלי)

הזרימה במערכת היא מעגלית וכוללת ארבעה רכיבים מרכזיים:

1. **User / Developer**: מזין את קובץ ה-App Spec (מפרט דרישות)
2. **Harness Logic (Python Orchestrator)**:
   - State Manager: טוען ושומר את המזהים של הפרויקט
   - Loop Controller: מודד את צריכת הטוקנים ומחליט מתי לבצע Reset
   - Tool Gateway: מתווך בין בקשות המודל לבין שרתי ה-MCP
3. **External Brain (Claude 3.5 Sonnet)**: מקבל את ה-Context הדחוס ומחזיר פעולות (Tool Calls)
4. **Tools & Persistence Layer**:
   - Linear API: ניהול המשימות (Source of Truth for Requirements)
   - Docker Container: סביבת הרצה מבודדת (Execution Environment)
   - Local Git: ניהול גרסאות הקוד (Source of Truth for Code)

### 3.2 מחזור החיים: הלולאה הרקורסיבית

הלוגיקה הטכנית של הלולאה Execute → Detect Limit → Pause → Summarize → Reset → Resume מיושמת באופן הבא:

#### שלב א': Execute (ביצוע)
הרתמה שולחת ל-Claude את ההיסטוריה הנוכחית + המשימה הפעילה מ-Linear. המודל מחזיר סדרה של קריאות לכלים (Tool Calls) כגון write_file, run_test. הרתמה מבצעת את הפעולות בתוך הקונטיינר ומחזירה את הפלט למודל.

#### שלב ב': Detect Limit (זיהוי גבולות)
לפני כל קריאה למודל, הרתמה בודקת שני פרמטרים:
- **Token Usage**: האם סך הטוקנים (Input + Output) חצה סף מוגדר (למשל, 80% מהתקציב לסשן)?
- **Logical Completion**: האם המודל סימן שהמשימה הסתיימה (באמצעות כלי ייעודי task_completed)?
- **Stagnation**: האם המודל חוזר על אותה שגיאה 3 פעמים ברציפות?

#### שלב ג': Pause & Summarize (עצירה וסיכום)
אם זוהה גבול:
1. הרתמה עוצרת את הוספת ההודעות החדשות להיסטוריה
2. הרתמה מזריקה "System Injection": "You are approaching the context limit. Please summarize your current progress into the handoff artifact format. Be extremely specific about what needs to be done next."
3. המודל מייצר את הטקסט ל-context_handoff.md

#### שלב ד': Reset & Resume (איפוס וחזרה)
1. **Persistence**: הרתמה מבצעת git commit עם הודעה אוטומטית המבוססת על הסיכום
2. **State Update**: עדכון הטיקט ב-Linear (הוספת הערה עם הסיכום)
3. **Clean Slate**: הרתמה מוחקת את כל רשימת ה-messages בזיכרון של Python
4. **Reload**: הרתמה טוענת מחדש את ה-System Prompt ואת ה-context_handoff.md החדש כהודעת המשתמש הראשונה
5. **Resume**: הלולאה מתחילה מחדש

### 3.3 מיקום שמירת המצב (State Storage Strategy)

המחקר מצביע על גישה היברידית כפתרון היציב ביותר:

- **Linear**: משמש כ-"Global State". שם נשמר מה צריך לעשות (Backlog) ומה נעשה (Done)
- **Git**: משמש כ-"Code State". מאפשר חזרה אחורה (Revert) אם סוכן מסוים "שבר" את הקוד
- **Local JSON (harness_state.json)**: משמש כ-"Session State". שומר מטא-דאטה טכני כגון: linear_project_id, current_ticket_id, last_git_hash. קובץ זה מאפשר לרתמה להתאושש מקריסה של הסקריפט עצמו ולהמשיך בדיוק מאותה נקודה

## 4. אינטגרציית כלים ופרוטוקול ההקשר (MCP Integration)

פרוטוקול ה-Model Context Protocol (MCP) הוא התקן החדש של Anthropic המאפשר למודלים להתחבר למערכות חיצוניות בצורה סטנדרטית. במקום "להדביק" פונקציות Python ישירות לתוך הקוד של הרתמה, אנו מקימים שרתי MCP עצמאיים.

### 4.1 ארכיטקטורת MCP ברתמה

אנו נשתמש בשני שרתי MCP נפרדים:
1. **Filesystem & Shell Server**: אחראי על האינטראקציה עם מערכת ההפעלה (בתוך ה-Sandbox)
2. **Linear Server**: אחראי על ניהול הפרויקט

השימוש ב-MCP מאפשר ניתוק צימוד (Decoupling). אם נרצה בעתיד להחליף את Linear ב-Jira, נצטרך רק להחליף את שרת ה-MCP, ללא שינוי בלוגיקה של הרתמה או בפרומפטים של הסוכן.

### 4.2 הקמת שרת MCP מותאם אישית

בעוד שקיימים שרתי MCP קהילתיים ל-Linear, המלצת המחקר היא לבנות שרת רזה ומותאם אישית כדי למנוע חשיפת יתר של ה-API.

#### אסטרטגיית הכלים (Tool Definition Strategy):

במקום לחשוף את כל ה-API של Linear, נחשוף רק פעולות "High Level":
- `linear_create_project(spec)`: פונקציית מקרו המייצרת פרויקט ומחזירה ID
- `linear_get_next_task(project_id)`: לוגיקה חכמה שמסננת ומחזירה את המשימה הרלוונטית ביותר
- `linear_complete_task(issue_id, summary)`: מעדכן סטטוס ומוסיף הערה

### 4.3 תחבורה (Transport)

הרתמה תתקשר עם שרתי ה-MCP באמצעות פרוטוקול stdio (Standard Input/Output). זוהי השיטה הפשוטה והמאובטחת ביותר לשימוש מקומי.

## 5. תזמור משימות: אינטגרציה עמוקה עם Linear

האינטגרציה עם Linear היא הלב הפועם של המערכת. היא הופכת את הסוכן מ"כותב קוד" ל"מנהל פרויקט".

### 5.1 משיכת כרטיסים וניהול היררכיה

Linear בנויה מהיררכיה של Organization → Team → Project → Issue. הרתמה חייבת לנווט בהיררכיה זו.

#### תהליך האתחול (The Bootstrapping Flow):
1. סוכן האתחול מקבל את ה-App Spec
2. הוא משתמש בכלי linear_create_project ליצירת "קונטיינר" למשימות
3. הוא מפרק את ה-Spec ל-20-50 משימות אטומיות
4. הוא משתמש בכלי linear_batch_create_issues כדי להזין אותן למערכת
5. קריטי: יש להזין את המשימות בסדר לוגי

### 5.2 תרגום כרטיסים להנחיות

כאשר סוכן הקידוד מושך כרטיס, הרתמה מבצעת "העשרה" (Enrichment) של המידע לפני שהוא מגיע למודל.

### 5.3 שימוש ב-GraphQL לביצועים

ה-API של Linear מבוסס GraphQL. השימוש ב-GraphQL קריטי כאן כדי לחסוך בטוקנים.

```graphql
query {
  issue(id: "LIN-123") {
    title
    description
    state { name }
    comments(last: 5) { body }
  }
}
```

## 6. מנגנוני כשל ובטיחות

### 6.1 זיהוי לולאות הזיה (Hallucination Loop Detection)

סוכנים נוטים לנסות את אותו פתרון שגוי שוב ושוב. פתרון טכני:
- הרתמה תשמור Hash של 3 הפקודות האחרונות ושל הפלטים שלהן
- אם Hash(Current) == Hash(Last), הרתמה מזהה לולאה
- פעולה מתקנת: הרתמה עוצרת ומזריקה הודעת מערכת אגרסיבית

### 6.2 בדיקת שפיות לקוד (Code Sanity Checks)

לפני ביצוע git commit, הרתמה תריץ סט בדיקות אוטומטי (Linter / Syntax Check).

### 6.3 בקרת עלויות (Cost Control)

- **תקציב לכל משימה**: מוגדר "תקציב טוקנים" לכל טיקט Linear
- **Circuit Breaker**: אם העלות הכוללת של הפרויקט חצתה סף, כל הרתמה עוצרת מיידית

## 7. אבטחה וארגז חול (Security & Sandboxing)

### 7.1 בידוד באמצעות Docker

הפתרון המנדטורי הוא הרצת כל פעולות הסוכן בתוך קונטיינר Docker.

- **הרתמה (Host)**: רצה על המחשב המארח, מנהלת את ה-LLM ואת Linear
- **הביצוע (Guest)**: רץ בתוך קונטיינר
- **תקשורת**: שרת ה-MCP מבצע את הפקודות בתוך הקונטיינר באמצעות docker exec

### 7.2 הגדרת Volume Mounts

```bash
docker run -v /host/path/to/project:/workspace -w /workspace python:3.9-slim
```

### 7.3 הגבלת רשת (Network Restriction)

שימוש ב-Docker Network המגבילה את התעבורה רק ל-Registries מוכרים (PyPI, NPM).

## 8. תוכנית בניה מפורטת (Step-by-Step Build Plan)

תוכנית זו מחולקת ל-4 פאזות:

### שלב 1: הלולאה הבסיסית (Basic Loop)
מטרה: יצירת מנוע שמסוגל לנהל שיחה רציפה עם "שכחה מבוקרת".

### שלב 2: התמדה וסיכום (Persistence & Handoff)
מטרה: מתן יכולת למערכת לזכור הקשר בין ריצות.

### שלב 3: אינטגרציית כלים ו-Docker (Tool/MCP Integration)
מטרה: חיבור הסוכן לעולם האמיתי בצורה מאובטחת.

### שלב 4: אינטגרציית Linear (Task Orchestration)
מטרה: אוטונומיה מלאה בניהול הפרויקט.

## 9. הנדסת פרומפטים: תבניות קריטיות

### 9.1 סוכן העבודה (The Worker Agent System Prompt)

```
You are an expert Full-Stack Developer operating within a controlled execution loop.
Your Goal: Complete the single task assigned to you in the "Current Context".

<system_constraints>
You have NO memory of previous sessions besides what is in "Global Context".
You must act autonomously. Do not ask the user for permission.
You must use the provided tools for all actions.
TDD (Test Driven Development) is MANDATORY.
</system_constraints>
```

### 9.2 סוכן הסיכום (The Summarizer Agent Prompt)

```
You are a Technical Documentation Specialist.
Your Goal: Compress the provided session transcript into a high-density "Handoff Artifact".
```

## 10. בחירת טכנולוגיה (Tech Stack Selection)

| רכיב | טכנולוגיה נבחרת | נימוק |
|------|-----------------|-------|
| שפת פיתוח | Python 3.10+ | השפה הדומיננטית ב-AI |
| ניהול משימות | Linear | API מהיר (GraphQL) |
| סביבת הרצה | Docker | חובה לאבטחה |
| מודל שפה | Claude 3.5 Sonnet | הטוב ביותר למשימות קידוד |
| זיכרון ארוך טווח | ללא Vector DB | קובץ context.md + grep |

## 11. ניתוח משווה: רתמה מותאמת אישית מול פתרונות מדף

### היתרונות של רתמה מותאמת אישית:
- **שליטה מוחלטת ב-Loop**: הקוד הוא שקוף
- **דיבאגינג**: הכל גלוי בלוגים
- **Handoff ספציפי**: ארכיטקטורה ייעודית

### המלצה:
עבור "Long-Running Developer Agent", הגישה של Custom Harness עדיפה משמעותית.

## 12. סיכום

התוכנית המוצגת מספקת מתווה שלם לבניית "עובד וירטואלי" המסוגל לתרום קוד אמיתי לפרויקטים מורכבים. הסוד טמון בהנדסת המערכת: הפירוק הקפדני של משימות ב-Linear, הבידוד המאובטח ב-Docker, ומעל הכל – פרוטוקול ה-Handoff שמבטיח רציפות קוגניטיבית.

---

# Technical Appendix: Implementation Details

## A. Detailed System Architecture & Logic Flow

### Class Structure

```python
class AgentHarness:
    def __init__(self):
        self.state = "IDLE"
        self.linear = LinearClient()
        self.docker = DockerSandbox()
        self.memory = []
        self.project_context = {}
        self.token_usage = 0

    def run(self):
        """Main Loop Entry Point"""
        if not self.load_project_state():
            self.run_initializer_agent()

        while True:
            task = self.linear.fetch_next_task()
            if not task:
                print("No tasks pending. Exiting.")
                break

            self.execute_coding_session(task)
            self.perform_handoff(task)
            self.reset_context()
```

## B. Linear Integration: GraphQL Deep Dive

### 1. Fetching Tasks

```graphql
query GetNextTask($teamId: String!) {
  team(id: $teamId) {
    issues(
      first: 1,
      filter: { state: { name: { eq: "Todo" } } },
      sort: { priority: { order: ASC } }
    ) {
      nodes {
        id
        title
        description
        identifier
        comments(last: 3) {
          nodes { body }
        }
      }
    }
  }
}
```

### 2. Updating Status

```graphql
mutation UpdateIssueStatus($issueId: String!, $stateId: String!) {
  issueUpdate(
    id: $issueId,
    input: { stateId: $stateId }
  ) {
    success
    issue {
      id
      updatedAt
    }
  }
}
```

## C. DockerSandbox Implementation

```python
import docker

class DockerSandbox:
    def __init__(self, workspace_path):
        self.client = docker.from_env()
        self.container = None
        self.workspace = workspace_path

    def start(self):
        """Starts a persistent container with volume mount"""
        self.container = self.client.containers.run(
            "python:3.9-slim",
            command="tail -f /dev/null",
            detach=True,
            volumes={self.workspace: {'bind': '/workspace', 'mode': 'rw'}},
            working_dir="/workspace",
            network_mode="host",
            mem_limit="2g"
        )

    def run_command(self, cmd):
        """Executes shell command inside container"""
        if not self.container:
            self.start()

        try:
            exit_code, output = self.container.exec_run(
                cmd,
                demux=True,
                workdir="/workspace"
            )
            return {
                "exit_code": exit_code,
                "stdout": output.decode() if output else "",
                "stderr": output.decode() if output else ""
            }
        except Exception as e:
            return {"error": str(e)}
```

## D. Tech Stack Recommendations

- **Python**: Chosen for the Orchestrator logic
- **Linear**: The optimal Task Manager
- **FastMCP**: Library for building tool servers
- **Claude 3.5 Sonnet**: The engine
- **SQLite (Optional)**: If state.json becomes too complex
