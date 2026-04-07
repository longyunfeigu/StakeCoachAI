# Database Migrations with Alembic

This directory contains database migration files managed by Alembic.

## Setup

1. Configure your database URL in `.env` file (nested style recommended):
   ```
   DATABASE__URL=postgresql+asyncpg://user:password@localhost:5432/dbname
   ```
   The tooling also falls back to `DATABASE_URL` for compatibility.

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Common Commands

### Create a new migration
```bash
# Auto-generate migration based on model changes
alembic revision --autogenerate -m "Description of changes"

# Create empty migration
alembic revision -m "Description of changes"
```

### Apply migrations
```bash
# Upgrade to latest version
alembic upgrade head

# Upgrade to specific version
alembic upgrade <revision>

# Upgrade one version
alembic upgrade +1
```

### Rollback migrations
```bash
# Downgrade one version
alembic downgrade -1

# Downgrade to specific version
alembic downgrade <revision>

# Downgrade to initial state
alembic downgrade base
```

### View migration history
```bash
# Show current version
alembic current

# Show migration history
alembic history

# Show migration history with details
alembic history --verbose
```

## Important Notes

1. **Model Location**: Update `alembic/env.py` to import your actual models:
   ```python
   # Replace the placeholder with your actual models
   from domain.models import Base
   # OR
   from infrastructure.database.models import Base
   ```

2. **Auto-generation**: For auto-generation to work properly, ensure all your models are imported in the `env.py` file.

3. **Migration Files**: Migration files are timestamped and stored in `alembic/versions/`

4. **Database Support**: Configured to work with PostgreSQL, MySQL, and SQLite. Default fallback is SQLite for development.
