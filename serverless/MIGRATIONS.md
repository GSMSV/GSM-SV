# Serverless Prisma migration rollout (PostgreSQL 16)

**Production gate: baseline any legacy database *before* merging/deploying this change.** The container now runs `npx prisma migrate deploy` before `npm start`; a migration failure stops startup. The existing `20240101000000_init` migration creates the same three `sv_*` tables that the former `setup-db.ts` created. Running it against a legacy database with those tables and no Prisma history fails (and a partial/modified schema is not safe to mark applied). Do not delete data, reset the database, run `prisma db push` or use `migrate resolve` to paper over drift. No live database was inspected for this PR.

## One-time pre-deployment checklist (operator, per database)

1. Schedule a maintenance window and pause serverless writes/rollout; coordinate with backend users of the shared PostgreSQL database. Take a **full** backup outside the container/volume, and prove it restores in an isolated environment before touching production. Example from the deployment host (keep the dump private):

   ```sh
   docker compose exec -T db pg_dump -U gsmsv -d gsmsv -Fc > gsmsv-before-serverless-baseline.dump
   ```

   Ensure sufficient free space, a verified restore, and a rollback owner. Do not log database credentials or dump contents in CI/PR comments.

2. Inspect the live database **before** running the new serverless image. With an operator's `psql` session on the target database, inspect the table existence, columns (types, nullability and defaults), indexes, PK/FK definitions, and migration history:

   ```sql
   SELECT to_regclass('public.sv_functions'), to_regclass('public.sv_triggers'),
          to_regclass('public.sv_execution_logs'), to_regclass('public._prisma_migrations');
   SELECT table_name, column_name, data_type, is_nullable, column_default
     FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name IN ('sv_functions','sv_triggers','sv_execution_logs')
    ORDER BY table_name, ordinal_position;
   SELECT tablename, indexname, indexdef FROM pg_indexes
    WHERE schemaname = 'public' AND tablename IN ('sv_functions','sv_triggers','sv_execution_logs')
    ORDER BY tablename, indexname;
   SELECT conrelid::regclass, conname, pg_get_constraintdef(oid)
     FROM pg_constraint WHERE conrelid IN ('public.sv_functions'::regclass,
       'public.sv_triggers'::regclass, 'public.sv_execution_logs'::regclass)
    ORDER BY conrelid::regclass::text, conname;
   -- Only if _prisma_migrations exists:
   SELECT migration_name, finished_at, rolled_back_at FROM public._prisma_migrations ORDER BY started_at;
   ```

   Compare *every* serverless table/column/default/nullability/index/constraint to `prisma/migrations/20240101000000_init/migration.sql`, not only table names. Check for partial tables and unexpected changes made since the original startup DDL. `prisma migrate resolve --applied` records a claim, **not** a schema comparison. If any object differs, any table is missing, or migration history is failed/ambiguous, **stop** and reconcile manually on a restored copy first; do not mark the baseline applied. Query the history table only when it exists. Keep unrelated backend tables intact.

3. If all three tables exactly match the initial migration, have data to preserve, and the `_prisma_migrations` table is **absent**, run this **once**, using the approved image with this migration file, against the same target database. Run from the deployment host, not a developer machine with a production URL. The container's normal CMD encodes literal `#` in `DATABASE_URL`; use the identical normalization for this one-off command:

   ```sh
   docker compose run --rm --no-deps --entrypoint sh serverless -c 'export DATABASE_URL="$(echo "$DATABASE_URL" | sed "s/#/%23/g")" && npx prisma migrate resolve --applied 20240101000000_init'
   ```

   Do **not** baseline a fresh database (no `sv_*` tables): let `migrate deploy` apply the init migration. If `_prisma_migrations` exists, inspect it and use `npx prisma migrate status` instead; do not repeat `resolve` on an already applied migration. If only some tables exist, stop and restore/reconcile manually; automatic baseline is intentionally forbidden.

4. Verify `npx prisma migrate status` shows the expected history, then deploy/start serverless. Confirm `migrate deploy` succeeds, the service becomes healthy, and existing function/trigger/log counts and representative records match the pre-deployment snapshot. A failed migration exits before the HTTP server starts. A failed/uncertain verification blocks rollout; investigate against the backup rather than deleting or recreating tables.

## Rollback

Stop serverless and restore the previous application image. The baseline record alone does not change the existing `sv_*` data or tables; if a later migration changed schema, rolling back code alone does **not** roll back the database. Restore the verified full backup in a coordinated maintenance window after assessing writes since backup. Never blindly drop `_prisma_migrations` or reset the shared database. For future migrations, review SQL, locks, write downtime and rollback before deploying; the current baseline is a metadata registration, while the initial migration creates tables/indexes and FKs on a fresh database.
