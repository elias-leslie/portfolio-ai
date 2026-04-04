import { cpSync, existsSync, mkdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const frontendDir = dirname(scriptDir);
const standaloneDir = join(frontendDir, '.next', 'standalone');
const standaloneServer = join(standaloneDir, 'server.js');
const standaloneNextDir = join(standaloneDir, '.next');

function syncDirectory(sourceDir, targetDir) {
  if (!existsSync(sourceDir)) {
    return;
  }

  rmSync(targetDir, { force: true, recursive: true });
  mkdirSync(dirname(targetDir), { recursive: true });
  cpSync(sourceDir, targetDir, { recursive: true });
}

if (!existsSync(standaloneServer)) {
  console.error(
    'Missing .next/standalone/server.js. Run `pnpm build` before `pnpm start`.',
  );
  process.exit(1);
}

mkdirSync(standaloneNextDir, { recursive: true });
syncDirectory(join(frontendDir, '.next', 'static'), join(standaloneNextDir, 'static'));
syncDirectory(join(frontendDir, 'public'), join(standaloneDir, 'public'));

const child = spawn(process.execPath, ['server.js'], {
  cwd: standaloneDir,
  env: process.env,
  stdio: 'inherit',
});

child.on('error', (error) => {
  console.error('Failed to start Next standalone server:', error);
  process.exit(1);
});

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }

  process.exit(code ?? 0);
});
