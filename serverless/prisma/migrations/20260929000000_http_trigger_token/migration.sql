-- Existing HTTP triggers remain public (NULL hash). New HTTP triggers get a SHA-256 digest.
ALTER TABLE "sv_triggers" ADD COLUMN IF NOT EXISTS "secretTokenHash" TEXT;
