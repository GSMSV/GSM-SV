const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '..');
const dockerfile = fs.readFileSync(path.join(root, 'Dockerfile'), 'utf8');
const match = dockerfile.match(/^CMD (\[.*\])$/m);

function startup(failMigration = false) {
  assert.ok(match, 'Dockerfile must have JSON-array CMD');
  const cmd = JSON.parse(match[1]);
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'serverless-startup-'));
  try {
    for (const executable of ['npx', 'npm']) {
      const file = path.join(dir, executable);
      fs.writeFileSync(file, `#!/bin/sh\nprintf '%s\\n' '${executable}:'"$*" >> "$STARTUP_LOG"\nprintf 'URL=%s\\n' "$DATABASE_URL" >> "$STARTUP_LOG"\n${executable === 'npx' ? 'exit "$MIGRATION_EXIT"' : ''}\n`, { mode: 0o755 });
    }
    const log = path.join(dir, 'calls');
    const result = spawnSync(cmd[0], cmd.slice(1), {
      env: { ...process.env, PATH: `${dir}:${process.env.PATH}`, STARTUP_LOG: log, MIGRATION_EXIT: failMigration ? '7' : '0', DATABASE_URL: 'postgresql://user:p#ss@db:5432/gsmsv' },
      encoding: 'utf8', cwd: root,
    });
    return { status: result.status, calls: fs.existsSync(log) ? fs.readFileSync(log, 'utf8') : '', stderr: result.stderr };
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

test('migration runs before application with encoded URL', () => {
  const result = startup();
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.calls, /^npx:prisma migrate deploy\nURL=postgresql:\/\/user:p%23ss@db:5432\/gsmsv\nnpm:start\n/m);
});

test('migration failure prevents application startup', () => {
  const result = startup(true);
  assert.notEqual(result.status, 0);
  assert.doesNotMatch(result.calls, /npm:start/);
});

test('bootstrap does not invoke manual DDL setup', () => {
  const entry = fs.readFileSync(path.join(root, 'src/index.ts'), 'utf8');
  assert.doesNotMatch(entry, /setupDb|setup-db/);
  assert.equal(fs.existsSync(path.join(root, 'src/setup-db.ts')), false);
});
