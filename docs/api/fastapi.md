# FastAPI Application

## סקירה

FastAPI REST API עבור Agent Platform.

```python
from src.api.main import app
import uvicorn

# Run the application
uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Base URL:** `http://localhost:8000`
**API Docs:** `http://localhost:8000/docs` (Swagger UI)
**ReDoc:** `http://localhost:8000/redoc` (Alternative docs)

---

## Application Configuration

### App Metadata

```python
app = FastAPI(
    title="Agent Platform API",
    description="REST API for autonomous AI agent creation and orchestration",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)
```

### CORS Middleware

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
```

!!! warning "Production Security"
    CORS `allow_origins=["*"]` מתאים ל-development בלבד.
    ב-production יש להגביל ל-domains ספציפיים.

---

## Lifecycle Events

### Startup Event

```python
@app.on_event("startup")
async def startup_event():
    """Run on application startup.

    Initialize database connection pool and perform health checks.
    """
    # TODO: Initialize database connection
    pass
```

**Planned Actions:**
- Initialize database connection pool
- Create tables if needed (`create_db_and_tables()`)
- Verify GCP Secret Manager connectivity
- Load configuration from environment

### Shutdown Event

```python
@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown.

    Close database connections and cleanup resources.
    """
    # TODO: Close database connection
    pass
```

**Planned Actions:**
- Close database connections (`close_db_connection()`)
- Cleanup temporary resources
- Graceful shutdown of running tasks

---

## API Endpoints

### Health Check Endpoints

#### GET /health

בדיקת בריאות המערכת.

**Response Model:** `HealthResponse`

```json
{
  "status": "healthy",
  "timestamp": "2026-01-11T18:00:00Z",
  "version": "0.1.0",
  "database": "not_connected"
}
```

**Status Values:**
- `healthy` - System is operational
- `degraded` - Partial functionality
- `unhealthy` - System is down

**Example:**

```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.get("http://localhost:8000/health")
    data = response.json()
    print(f"Status: {data['status']}")
```

#### GET /

מידע בסיסי על ה-API.

**Response:** `dict[str, str]`

```json
{
  "name": "Agent Platform API",
  "version": "0.1.0",
  "docs": "/docs",
  "health": "/health"
}
```

---

## Response Models

### HealthResponse

::: src.api.routes.health.HealthResponse
    options:
      show_root_heading: true
      heading_level: 4

```python
from pydantic import BaseModel
from datetime import datetime

class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: datetime
    version: str
    database: str = "not_connected"
```

---

## Running the Application

### Development Mode

```bash
# Using uvicorn directly
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Using the module
python -m src.api.main
```

### Production Mode

```bash
# With Gunicorn + uvicorn workers
gunicorn src.api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ ./src/
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Railway Deployment

```toml
# railway.toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "uvicorn src.api.main:app --host 0.0.0.0 --port $PORT"
```

---

## Testing

### Using TestClient

```python
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_health_endpoint():
    """Test health check returns 200."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert data["version"] == "0.1.0"
```

### Async Testing

```python
import pytest
from httpx import AsyncClient
from src.api.main import app

@pytest.mark.asyncio
async def test_health_check_async():
    """Test health check with async client."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
```

---

## Architecture

### Router Organization

```python
# Main app
from src.api.main import app

# Health check routes
from src.api.routes import health
app.include_router(health.router, tags=["health"])

# Future routes
from src.api.routes import agents
app.include_router(agents.router, prefix="/agents", tags=["agents"])
```

### Dependency Injection

FastAPI's dependency injection משמש לניהול database sessions:

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.database import get_session

@app.get("/agents")
async def get_agents(session: AsyncSession = Depends(get_session)):
    """Get all agents - session מנוהל אוטומטית."""
    result = await session.execute(select(Agent))
    return result.scalars().all()
```

---

## Next Steps (Phase 3.2)

Planned endpoints for Agent Factory:

- `POST /agents` - Create agent from natural language
- `GET /agents` - List all agents
- `GET /agents/{id}` - Get specific agent
- `PUT /agents/{id}` - Update agent
- `DELETE /agents/{id}` - Delete agent
- `POST /agents/{id}/execute` - Trigger agent execution
- `GET /agents/{id}/tasks` - Get agent execution history
