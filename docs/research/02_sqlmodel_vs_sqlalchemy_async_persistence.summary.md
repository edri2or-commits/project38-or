# Summary: SQLModel vs SQLAlchemy - Async Persistence

**Source**: `research/02_sqlmodel_vs_sqlalchemy_async_persistence.md`

---

## Summary

Strategic analysis of persistence layer options for async FastAPI systems on Railway with PostgreSQL. Recommends a **hybrid approach**: SQLModel for model definition + SQLAlchemy 2.0 for complex queries.

**Key Findings:**
- SQLModel unifies Pydantic validation with SQLAlchemy ORM (solves "Double Declaration Problem")
- asyncpg is the optimal driver for PostgreSQL (Rust-level performance)
- Railway requires specific SSL and URL handling
- `expire_on_commit=False` is mandatory for async sessions

---

## Actionable Practices

1. **Database URL Parsing (Railway):**
   ```python
   url = url.replace("postgres://", "postgresql+asyncpg://", 1)
   ```

2. **SSL Configuration:**
   ```python
   connect_args = {"ssl": "require"}  # For Railway production
   ```

3. **Session Factory Settings:**
   ```python
   async_sessionmaker(
       expire_on_commit=False,  # Critical for async
       autoflush=False,
       pool_pre_ping=True       # Cloud resilience
   )
   ```

4. **Eager Loading Required:**
   - Use `selectinload()` for relationships
   - Lazy loading causes `MissingGreenlet` error in async

5. **Version Pinning:**
   - Pin `sqlmodel`, `pydantic`, `sqlalchemy` together
   - Avoid Pydantic v1/v2 conflicts

---

## Risks / Assumptions

| Risk | Impact | Mitigation |
|------|--------|------------|
| SQLModel maintenance lag | Delayed security patches | Monitor releases; use SQLAlchemy Core for complex queries |
| Pydantic v1/v2 conflict | Dependency hell | Strict pinning in pyproject.toml |
| asyncpg strict typing | Runtime DataError | Explicit type casting |
| Lazy loading in async | Crash (MissingGreenlet) | Always eager load |

**Assumptions:**
- PostgreSQL on Railway
- Python 3.10+
- FastAPI with Pydantic v2

---

## Architecture Decisions Impact

| Decision | Implication |
|----------|-------------|
| Use SQLModel | 40% less boilerplate, single model for API + DB |
| Use asyncpg | Best performance, but requires careful SSL config |
| Hybrid queries | SQLModel defines, SQLAlchemy Core for joins/CTEs |
| Repository Pattern | Testability, session management isolation |

**Recommended Stack:**
- `sqlmodel ^0.0.16`
- `sqlalchemy ^2.0.25`
- `asyncpg ^0.29.0`
- `pydantic ^2.6.0`
