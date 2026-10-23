# Serverless Prisma migration rollout (PostgreSQL 16)

**Production gate: inspect and, if necessary, baseline each legacy database before merging/deploying #114.** The new image runs `npx prisma migrate deploy` before `npm start` and exits on migration failure. `20240101000000_init` creates the three `sv_*` tables from the former `setup-db.ts`; running it against pre-existing tables without Prisma history fails. `migrate resolve --applied` only records a claim; it does not inspect or change the schema. No live database was inspected for this PR. Do not reset data, run `prisma db push`, or resolve a migration to hide drift.

## Supported states and merge order (#113 / #114)

- **Empty database:** no `sv_*` tables and no `_prisma_migrations`: do not baseline. Let `migrate deploy` create them.
- **Legacy database, no Prisma history:** all three tables must match the initial migration **exactly**, except that `public.sv_triggers."secretTokenHash"` may already exist from #113 as an *additional nullable `TEXT` column without a default*. That is the **only** permitted difference: no missing/changed columns, defaults, precision, indexes, constraints, or other additions. After a verified backup and rehearsal, resolve **only** `20240101000000_init` as applied; then run `migrate deploy` from the approved image. When #113's `20260929000000_http_trigger_token` migration is in that image, its `ADD COLUMN IF NOT EXISTS "secretTokenHash" TEXT` is a no-op if the column already exists, or adds it if absent. Its idempotence **does not validate an existing column's type/nullability/default**; that is why the inspection gate is mandatory. If the #113 migration is not in the image yet, it will run when that migration is later deployed.
- **Existing Prisma history:** inspect `_prisma_migrations` and run `prisma migrate status`. Do not resolve init again. If init is applied and the #113 column exists but its follow-on migration is pending, inspect the column as below and let the approved image run the pending migration. If migration history is failed/ambiguous, or claims the follow-on migration succeeded but the column is absent/wrong, **stop**. An absent column with only init applied is expected before #113; its migration will add it on deployment.
- **Partial tables, any other drift, or uncertain history:** **deployment blocked**. Reconcile on an isolated restored copy with an operator-approved, data-preserving plan, then re-inspect. Never mark init applied on an unverified schema.

If #113 is merged/deployed **before** #114, its old startup path may have added the column without Prisma history. Use the allowed-column baseline route above; **rebase #114 on the merged #113** before merging it, resolve the `setup-db.ts` delete/modify conflict, retain #113's Prisma model and follow-on migration, and verify that the eventual image contains both migrations and `migrate deploy` records them. If #114 lands **first**, baseline legacy DBs before its rollout; when #113 is later integrated, **rebase #113 on the merged #114** and resolve its `setup-db.ts` deletion and `index.ts`/Dockerfile conflicts: retain migration-based startup, keep the follow-on migration and updated Prisma schema, and do not reintroduce runtime DDL. Recheck the resulting diff and test both migrations before deploying. Merging either stale branch as-is is not safe. Coordinate rolling instances: the old gateway does not enforce tokens, so stop all old instances before creating protected HTTP triggers; if rolling back to old code, disable protected triggers first (see #113 rollout guidance).

## One-time pre-deployment checklist (operator, per database)

1. Schedule a maintenance window, pause serverless writes and rollout, and coordinate with other users of the shared PostgreSQL database. Take a **full** backup outside the container/volume and prove it restores in an isolated environment before touching production. Example from the deployment host (keep the dump private):

   ```sh
   docker compose exec -T db pg_dump -U gsmsv -d gsmsv -Fc > gsmsv-before-serverless-baseline.dump
   ```

   Record row counts and representative records for all three tables. Ensure free space, a verified restore, and a rollback owner. Do not publish credentials, the dump, or token hashes in logs/CI/PR comments.

2. On the **same target database** with an operator's `psql` session, inspect existence, **all** columns including timestamp precision, defaults and nullability, indexes, PK/FK definitions, and migration history. Run the constraint query only after confirming all three tables exist (casts to `regclass` fail on missing tables). Read-only inspection:

   ```sql
   SELECT to_regclass('public.sv_functions'), to_regclass('public.sv_triggers'),
          to_regclass('public.sv_execution_logs'), to_regclass('public._prisma_migrations');
   SELECT c.table_name, c.ordinal_position, c.column_name, c.data_type,
          c.udt_name, c.datetime_precision, c.is_nullable, c.column_default,
          pg_catalog.format_type(a.atttypid, a.atttypmod) AS pg_type
     FROM information_schema.columns AS c
     JOIN pg_catalog.pg_namespace AS n ON n.nspname = c.table_schema
     JOIN pg_catalog.pg_class AS t ON t.relnamespace = n.oid AND t.relname = c.table_name
     JOIN pg_catalog.pg_attribute AS a ON a.attrelid = t.oid
                                    AND a.attname = c.column_name AND a.attnum > 0 AND NOT a.attisdropped
    WHERE c.table_schema = 'public'
      AND c.table_name IN ('sv_functions','sv_triggers','sv_execution_logs')
    ORDER BY c.table_name, c.ordinal_position;
   SELECT tablename, indexname, indexdef FROM pg_indexes
    WHERE schemaname = 'public' AND tablename IN ('sv_functions','sv_triggers','sv_execution_logs')
    ORDER BY tablename, indexname;
   SELECT conrelid::regclass, conname, contype, pg_get_constraintdef(oid)
     FROM pg_constraint WHERE conrelid IN ('public.sv_functions'::regclass,
       'public.sv_triggers'::regclass, 'public.sv_execution_logs'::regclass)
    ORDER BY conrelid::regclass::text, conname;
   -- ONLY when to_regclass('public._prisma_migrations') is non-null:
   SELECT migration_name, finished_at, rolled_back_at, logs
     FROM public._prisma_migrations ORDER BY started_at;
   ```

   Compare **every row** with `prisma/migrations/20240101000000_init/migration.sql` (not just table names), including `timestamp without time zone` with `datetime_precision = 3` / `pg_type = timestamp(3) without time zone`; the `createdAt` default is `CURRENT_TIMESTAMP`, while `updatedAt` has no DB default. Expected fields are exactly:

   | Table | Columns (`name`: type, where `?` means nullable) |
   | --- | --- |
   | `sv_functions` | `id`: TEXT; `name`: TEXT; `description`: TEXT?; `code`: TEXT; `compiledCode`: TEXT?; `runtime`: TEXT DEFAULT 'javascript'; `timeout`: INTEGER DEFAULT 30000; `memoryLimit`: INTEGER DEFAULT 128; `envVars`: TEXT DEFAULT '{}'; `status`: TEXT DEFAULT 'active'; `ownerId`: INTEGER; `createdAt`: TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP; `updatedAt`: TIMESTAMP(3) |
   | `sv_triggers` | `id`: TEXT; `functionId`: TEXT; `type`: TEXT; `httpMethod`: TEXT? DEFAULT 'ANY'; `cronExpr`: TEXT?; `enabled`: BOOLEAN DEFAULT true; `createdAt`: TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP; `updatedAt`: TIMESTAMP(3). **Only allowed extra:** `secretTokenHash`: TEXT?, no default. |
   | `sv_execution_logs` | `id`: TEXT; `functionId`: TEXT; `trigger`: TEXT; `status`: TEXT; `duration`: INTEGER; `logs`: TEXT DEFAULT '[]'; `error`: TEXT?; `requestBody`: TEXT?; `response`: TEXT?; `createdAt`: TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP |

   Every field without `?` is `NOT NULL`; fields without `DEFAULT` have no default. PostgreSQL may render string defaults with a `::text` cast; compare the semantics, not whitespace. Expected indexes **only**: primary-key btree indexes `sv_functions_pkey(id)`, `sv_triggers_pkey(id)`, `sv_execution_logs_pkey(id)`; unique btree `sv_functions_ownerId_name_key(ownerId, name)`; non-unique btree `sv_execution_logs_functionId_createdAt_idx(functionId, createdAt)`. Expected constraints **only**: those three primary keys and `sv_triggers_functionId_fkey` / `sv_execution_logs_functionId_fkey` referencing `sv_functions(id)` with `ON DELETE CASCADE ON UPDATE CASCADE`. Compare index uniqueness, column order, methods, predicates and expressions, FK targets/actions, and table/column ownership. Any extra/missing/altered object, different timestamp precision (e.g. `timestamp(6)`), or an existing `secretTokenHash` that is non-TEXT, NOT NULL, or has a default **blocks baseline**. Check the source migration SQL and #113 follow-on SQL again at the chosen deployment commit; do not infer compatibility from `IF NOT EXISTS`.

3. Rehearse the exact baseline and `migrate deploy` with the chosen image on an isolated restored copy, and compare schema and row counts/representative records before and after. If all three live tables pass step 2, history is **absent**, the rehearsal succeeds, and the backup is verified, run **once** on the deployment host (not a developer machine with a production URL). The container's CMD encodes literal `#` in `DATABASE_URL`; use the same normalization:

   ```sh
   docker compose run --rm --no-deps --entrypoint sh serverless -c 'export DATABASE_URL="$(echo "$DATABASE_URL" | sed "s/#/%23/g")" && npx prisma migrate resolve --applied 20240101000000_init'
   ```

   Re-inspect history immediately. If the schema has changed since inspection, or another actor has initialized migration history, **stop** and re-evaluate; never repeat the resolve blindly. Fresh databases do not need this step.

4. Using the approved image, run `npx prisma migrate status` with the same URL normalization, then deploy/start serverless. Confirm `migrate deploy` succeeds, expected migration names appear as finished in history, the service becomes healthy, and row counts and representative records are unchanged. If #113 is included, verify `secretTokenHash` is nullable TEXT with no default and existing hashes are unchanged. Failed/uncertain verification blocks rollout; investigate on a restored copy, never delete/recreate tables.

## Rollback

Stop serverless and restore the previous application image only after assessing compatibility with the existing schema. Baseline registration alone changes no `sv_*` data or tables; the #113 follow-on migration adds a nullable column and must **not** be undone by dropping it while protected triggers exist (that would destroy hashes and potentially expose those triggers on old gateway code). Stop/disable protected triggers and eliminate old gateway instances before any rollback that could expose them. For a destructive or incompatible change, coordinate a maintenance window and restore the verified full backup **only after reconciling writes since the backup**. Never blindly drop `secretTokenHash` or `_prisma_migrations`, reset the shared database, or assume an application rollback reverses a migration. If data-preserving rollback cannot be demonstrated, keep the deployment blocked and escalate to the operator.
