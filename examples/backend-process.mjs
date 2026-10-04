// Single-input adapter example; no Chrono routes are changed.
import { spawn } from 'node:child_process';
import { isAbsolute, basename, join } from 'node:path';
import { access } from 'node:fs/promises';

export function processMedia(executable, input, outputDir, {
  level = 'high', signal, timeoutMs = 30 * 60 * 1000, onProgress = () => {},
} = {}) {
  if (![executable, input, outputDir].every(isAbsolute)) {
    return Promise.reject(new Error('Absolute executable, input and output paths required'));
  }
  if (!['base', 'medium', 'high', 'off'].includes(level)) {
    return Promise.reject(new Error('Unsupported level'));
  }
  if (signal?.aborted) return Promise.reject(new Error('Processing aborted'));
  return new Promise((resolve, reject) => {
    const args = ['--json', '--strict', '-o', outputDir];
    args.push(...(level === 'off' ? ['--no-faces'] : ['--level', level]), '--', input);
    const child = spawn(executable, args, {
      shell: false, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '', carry = '', failure;
    let total = 0;
    const stop = (message) => {
      failure ??= new Error(message);
      child.kill('SIGKILL');
    };
    const timer = setTimeout(() => stop('Processing timeout'), timeoutMs);
    const abort = () => stop('Processing aborted');
    signal?.addEventListener('abort', abort, { once: true });
    child.stdout.setEncoding('utf8');
    child.stderr.setEncoding('utf8');
    child.stdout.on('data', (chunk) => {
      stdout += chunk;
      if (stdout.length > 1024 * 1024) stop('Report too large');
    });
    child.stderr.on('data', (chunk) => {
      total += chunk.length;
      if (total > 16 * 1024 * 1024) { stop('Diagnostics too large'); return; }
      const lines = (carry + chunk).split(/\r?\n/);
      carry = lines.pop();
      if (carry.length > 64 * 1024) { stop('Diagnostic line too large'); return; }
      for (const line of lines) {
        if (!line.startsWith('__PROGRESS__ ')) continue;
        try {
          const event = JSON.parse(line.slice('__PROGRESS__ '.length));
          if (typeof event.stage !== 'string' || !Number.isInteger(event.percent)
              || event.percent < 0 || event.percent > 100) throw new Error('Invalid progress');
          onProgress(event);
        } catch { stop('Invalid progress or progress callback failed'); }
      }
    });
    child.on('error', (error) => { failure ??= error; });
    child.on('close', async (code, killedBy) => {
      clearTimeout(timer);
      signal?.removeEventListener('abort', abort);
      if (failure) { reject(failure); return; }
      if (killedBy) { reject(new Error('Processing interrupted')); return; }
      try {
        const rows = stdout.trim().split(/\r?\n/).filter(Boolean).map(JSON.parse);
        if (rows.length !== 1) throw new Error('Expected one report');
        const report = rows[0];
        if (code !== 0 || report.status !== 'ok') {
          const error = new Error(`Blurry failed (${code}, ${report.status})`);
          error.exitCode = code;
          error.report = report;
          throw error;
        }
        if (typeof report.output !== 'string' || basename(report.output) !== report.output
            || report.output === '.' || report.output === '..') throw new Error('Invalid output name');
        const output = join(outputDir, report.output);
        await access(output);
        resolve({ report, output });
      } catch (error) { reject(error); }
    });
  });
}
