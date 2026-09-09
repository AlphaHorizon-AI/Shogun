import assert from 'node:assert/strict';
import test from 'node:test';
import { evaluateAudit } from './check-npm-audit.mjs';

const result = (vulnerabilities = {}, status = 0) => ({
  status, stdout: JSON.stringify({ auditReportVersion: 2, vulnerabilities }),
});

test('accepts a completed clean audit', () => {
  assert.deepEqual(evaluateAudit(result()), { blocked: [], lowerSeverity: [] });
});

test('blocks all high and critical findings, including the expired exception', () => {
  const audit = result({
    router: { severity: 'high', via: [{ url: 'https://github.com/advisories/GHSA-qwww-vcr4-c8h2' }] },
    other: { severity: 'critical' },
  }, 1);
  assert.deepEqual(evaluateAudit(audit).blocked, ['router', 'other']);
});

test('reports moderate findings separately from security exceptions', () => {
  assert.deepEqual(evaluateAudit(result({ tool: { severity: 'moderate' } }, 1)), {
    blocked: [], lowerSeverity: ['tool'],
  });
});

for (const [name, audit] of Object.entries({
  'network failure JSON': { status: 1, stdout: JSON.stringify({ error: { code: 'ECONNRESET' } }) },
  'API error with empty findings': { status: 1, stdout: JSON.stringify({ auditReportVersion: 2, error: {}, vulnerabilities: {} }) },
  'invalid JSON': { status: 0, stdout: '<html>proxy error</html>' },
  'missing report': { status: 0, stdout: '{}' },
  'unknown report version': { status: 0, stdout: JSON.stringify({ auditReportVersion: 3, vulnerabilities: {} }) },
  'unexpected exit status': result({}, 2),
  'failed audit with empty findings': result({}, 1),
  'unknown severity': result({ tool: { severity: 'unknown' } }),
  'malformed findings': result([]),
  'null report': { status: 0, stdout: 'null' },
  'spawn timeout': { ...result(), error: new Error('ETIMEDOUT') },
  'terminated process': { ...result(), status: null },
})) {
  test(`rejects ${name}`, () => assert.throws(() => evaluateAudit(audit)));
}
