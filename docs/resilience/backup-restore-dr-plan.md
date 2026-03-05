# Backup, Restore, and Disaster Recovery Plan

## Backup Strategy
1. Run backups at least every 6 hours for production databases.
2. Keep encrypted backups in two regions/providers.
3. Retention policy:
   - Daily backups: 14 days
   - Weekly backups: 8 weeks
   - Monthly backups: 12 months

## Tooling
- Backup script: `python scripts/db_backup.py --out-dir backups`
- Restore script: `python scripts/db_restore.py --backup-file <file> --manifest-file <manifest> --force`
- Drill script: `python scripts/backup_restore_drill.py`

## Restore Procedure
1. Validate checksum against backup manifest.
2. Restore to staging first and verify row counts + app health.
3. Restore production during maintenance window or failover event.
4. Run post-restore validation:
   - `/health/ready` = 200
   - login flow
   - import/resolve/filter smoke flow

## RTO/RPO Targets
- Recovery Time Objective (RTO): 60 minutes
- Recovery Point Objective (RPO): 15 minutes

## Disaster Recovery Drill Cadence
- Weekly automated drill in CI (`dr-backup-restore-drill.yml`)
- Monthly manual full-environment failover rehearsal
