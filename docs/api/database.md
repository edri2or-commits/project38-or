# Database Connection Management

## סקירה

מודול `src.api.database` מנהל את החיבור ל-PostgreSQL באמצעות SQLAlchemy async ו-SQLModel.

```python
from src.api.database import get_session, create_db_and_tables
from sqlalchemy.ext.asyncio import AsyncSession

# יצירת טבלאות
await create_db_and_tables()

# שימוש ב-session עם FastAPI
from fastapi import Depends

@app.get("/agents")
async def get_agents(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Agent))
    return result.scalars().all()
```

## Configuration

### DATABASE_URL

החיבור ל-PostgreSQL נקבע דרך משתנה הסביבה `DATABASE_URL`:

```bash
export DATABASE_URL="postgresql+asyncpg://user:password@host:port/database"
```

**Default:** `postgresql+asyncpg://postgres:postgres@localhost:5432/agentplatform`

### Connection Pool Settings

- **pool_size:** 20 connections
- **max_overflow:** 10 additional connections
- **echo:** Enabled when `DEBUG=true`

---

## Functions

::: src.api.database.create_db_and_tables
    options:
      show_root_heading: true
      heading_level: 3

::: src.api.database.get_session
    options:
      show_root_heading: true
      heading_level: 3

::: src.api.database.check_database_connection
    options:
      show_root_heading: true
      heading_level: 3

::: src.api.database.close_db_connection
    options:
      show_root_heading: true
      heading_level: 3

---

## Usage Examples

### Application Startup

```python
from src.api.database import create_db_and_tables

@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup."""
    await create_db_and_tables()
```

### Health Check

```python
from src.api.database import check_database_connection

@app.get("/health")
async def health_check():
    """Check if database is reachable."""
    db_healthy = await check_database_connection()
    return {"database": "healthy" if db_healthy else "unhealthy"}
```

### Application Shutdown

```python
from src.api.database import close_db_connection

@app.on_event("shutdown")
async def shutdown_event():
    """Close database connections on shutdown."""
    await close_db_connection()
```

---

## Architecture

### Async Pattern

הכל async - SQLAlchemy async engine + asyncpg driver:

```python
# ✅ CORRECT - async pattern
async with async_session_maker() as session:
    result = await session.execute(select(Agent))
    agents = result.scalars().all()

# ❌ WRONG - sync pattern won't work
session = Session()
agents = session.query(Agent).all()
```

### Connection Pooling

Engine משתמש ב-connection pool:
- **Minimum connections:** 20 (pool_size)
- **Maximum connections:** 30 (pool_size + max_overflow)
- **Automatic recycling:** connections returned to pool after use

!!! info "Railway Deployment"
    Connection pool מתאים ל-Railway's PostgreSQL limits.
    Pool pre-ping מבטיח connections תקינים.
