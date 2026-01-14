# n8n Workflows

This directory contains n8n workflow configurations for automation.

## Workflows

- **Database Backup - Daily Automated**: Created via `src/workflows/database_backup_workflow.py`
- **Database Backup - Weekly Verification**: Created via `src/workflows/database_backup_workflow.py`
- **Cost Alerts**: Created via `src/workflows/cost_alert_workflow.py`

## Usage

Workflows are generated programmatically using Python modules in `src/workflows/`.

See:
- `src/workflows/database_backup_workflow.py` - Database backup workflows
- `src/workflows/cost_alert_workflow.py` - Cost monitoring workflows
- `docs/operations/disaster-recovery.md` - Backup documentation
- `docs/operations/performance-baseline.md` - Performance monitoring documentation
