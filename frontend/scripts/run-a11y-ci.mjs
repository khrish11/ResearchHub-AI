import { spawn } from 'node:child_process';

const SERVER_URL = 'http://127.0.0.1:4173';
const START_TIMEOUT_MS = 120000;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForServer(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url, { redirect: 'manual' });
      if (response.status >= 200 && response.status < 500) {
        return;
      }
    } catch {
      // retry
    }
    await sleep(800);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

async function terminateProcessTree(child) {
  if (!child || child.killed) return;
  if (process.platform === 'win32') {
    await new Promise((resolve) => {
      const killer = spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], {
        stdio: 'ignore',
      });
      killer.on('close', () => resolve(undefined));
      killer.on('error', () => resolve(undefined));
    });
    return;
  }
  child.kill('SIGTERM');
}

async function main() {
  const preview = spawn(
    process.platform === 'win32'
      ? 'npm run preview -- --host 127.0.0.1 --port 4173 --strictPort'
      : 'npm run preview -- --host 127.0.0.1 --port 4173 --strictPort',
    { stdio: 'inherit', shell: true },
  );

  try {
    await waitForServer(SERVER_URL, START_TIMEOUT_MS);

    const pa11y = spawn('npx pa11y-ci --config .pa11yci.json', {
      stdio: 'inherit',
      shell: true,
    });
    const exitCode = await new Promise((resolve) => pa11y.on('close', resolve));
    if (exitCode !== 0) {
      process.exitCode = Number(exitCode || 1);
    }
  } finally {
    await terminateProcessTree(preview);
  }
}

main().catch(async (err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exitCode = 1;
});
