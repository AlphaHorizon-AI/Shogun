#!/usr/bin/env node

import { spawnSync } from 'node:child_process';
import process from 'node:process';

const APPROVED_ADVISORIES = new Set([
  'https://github.com/advisories/GHSA-qwww-vcr4-c8h2',
]);
const windows = process.platform === 'win32';
const audit = spawnSync(
  windows ? process.env.ComSpec : 'npm',
  windows ? ['/d', '/s', '/c', 'npm audit --json'] : ['audit', '--json'],
  {
  cwd: process.argv[2] || process.cwd(),
  encoding: 'utf8',
  shell: false,
  },
);

if (audit.error) {
  process.stderr.write(`Could not execute npm audit: ${audit.error.message}\n`);
  process.exit(1);
}

let report;
try {
  report = JSON.parse(audit.stdout);
} catch {
  process.stderr.write(audit.stderr || audit.stdout || 'npm audit returned invalid JSON\n');
  process.exit(audit.status || 1);
}

const vulnerabilities = report.vulnerabilities || {};
const memo = new Map();

function approved(name, trail = new Set()) {
  if (memo.has(name)) return memo.get(name);
  if (trail.has(name)) return false;
  const finding = vulnerabilities[name];
  if (!finding) return false;
  if (!['high', 'critical'].includes(finding.severity)) return true;

  const nextTrail = new Set(trail).add(name);
  const result = finding.via.every(via => {
    if (typeof via === 'string') return approved(via, nextTrail);
    return APPROVED_ADVISORIES.has(via.url);
  });
  memo.set(name, result);
  return result;
}

const blocked = Object.keys(vulnerabilities).filter(name => !approved(name));
if (blocked.length) {
  process.stderr.write(`Unapproved High/Critical npm findings: ${blocked.join(', ')}\n`);
  process.stderr.write(JSON.stringify(report, null, 2));
  process.exit(1);
}

const excepted = Object.keys(vulnerabilities).filter(name => approved(name));
if (excepted.length) {
  process.stdout.write(
    `Approved temporary exception only: GHSA-qwww-vcr4-c8h2 (${excepted.join(', ')}). ` +
    'See docs/security/frontend-dependency-exceptions.md.\n',
  );
} else {
  process.stdout.write('No High or Critical npm findings.\n');
}
