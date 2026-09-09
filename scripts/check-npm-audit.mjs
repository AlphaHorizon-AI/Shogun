#!/usr/bin/env node

import { spawnSync } from 'node:child_process';
import process from 'node:process';
import { pathToFileURL } from 'node:url';

export function evaluateAudit(audit) {
  if (audit.error || ![0, 1].includes(audit.status)) {
    throw new Error('npm audit failed; dependency security could not be verified.');
  }
  let report;
  try {
    report = JSON.parse(audit.stdout);
  } catch {
    throw new Error('npm audit returned invalid JSON.');
  }
  if (!report || report.error || report.auditReportVersion !== 2
      || !report.vulnerabilities || typeof report.vulnerabilities !== 'object'
      || Array.isArray(report.vulnerabilities)) {
    throw new Error('npm audit did not return a valid vulnerability report.');
  }
  const findings = Object.entries(report.vulnerabilities);
  const severities = new Set(['info', 'low', 'moderate', 'high', 'critical']);
  if (findings.some(([, finding]) => !finding || !severities.has(finding.severity))
      || (audit.status === 1 && findings.length === 0)) {
    throw new Error('npm audit returned an inconsistent vulnerability report.');
  }
  return {
    blocked: findings.filter(([, finding]) => ['high', 'critical'].includes(finding.severity)).map(([name]) => name),
    lowerSeverity: findings.filter(([, finding]) => !['high', 'critical'].includes(finding.severity)).map(([name]) => name),
  };
}

function main() {
  const windows = process.platform === 'win32';
  const audit = spawnSync(
    windows ? process.env.ComSpec : 'npm',
    windows ? ['/d', '/s', '/c', 'npm audit --json'] : ['audit', '--json'],
    { cwd: process.argv[2] || process.cwd(), encoding: 'utf8', shell: false, timeout: 120_000 },
  );
  try {
    const { blocked, lowerSeverity } = evaluateAudit(audit);
    if (blocked.length) {
      process.stderr.write(`High/Critical npm findings: ${blocked.join(', ')}\n`);
      process.exitCode = 1;
      return;
    }
    process.stdout.write('No High or Critical npm findings.\n');
    if (lowerSeverity.length) {
      process.stdout.write(`Lower-severity npm findings: ${lowerSeverity.join(', ')}.\n`);
    }
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main();
