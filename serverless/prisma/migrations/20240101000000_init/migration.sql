-- CreateTable
CREATE TABLE "sv_functions" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "code" TEXT NOT NULL,
    "compiledCode" TEXT,
    "runtime" TEXT NOT NULL DEFAULT 'javascript',
    "timeout" INTEGER NOT NULL DEFAULT 30000,
    "memoryLimit" INTEGER NOT NULL DEFAULT 128,
    "envVars" TEXT NOT NULL DEFAULT '{}',
    "status" TEXT NOT NULL DEFAULT 'active',
    "ownerId" INTEGER NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "sv_functions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "sv_triggers" (
    "id" TEXT NOT NULL,
    "functionId" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "httpMethod" TEXT DEFAULT 'ANY',
    "cronExpr" TEXT,
    "enabled" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "sv_triggers_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "sv_execution_logs" (
    "id" TEXT NOT NULL,
    "functionId" TEXT NOT NULL,
    "trigger" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "duration" INTEGER NOT NULL,
    "logs" TEXT NOT NULL DEFAULT '[]',
    "error" TEXT,
    "requestBody" TEXT,
    "response" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "sv_execution_logs_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "sv_functions_ownerId_name_key" ON "sv_functions"("ownerId", "name");

-- CreateIndex
CREATE INDEX "sv_execution_logs_functionId_createdAt_idx" ON "sv_execution_logs"("functionId", "createdAt");

-- AddForeignKey
ALTER TABLE "sv_triggers" ADD CONSTRAINT "sv_triggers_functionId_fkey" FOREIGN KEY ("functionId") REFERENCES "sv_functions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sv_execution_logs" ADD CONSTRAINT "sv_execution_logs_functionId_fkey" FOREIGN KEY ("functionId") REFERENCES "sv_functions"("id") ON DELETE CASCADE ON UPDATE CASCADE;
