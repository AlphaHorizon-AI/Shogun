import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const i18nDir = join(root, 'src', 'i18n');
const wizard = await readFile(join(root, 'src', 'pages', 'SetupWizard.tsx'), 'utf8');
const languageFiles = (await readdir(i18nDir)).filter(name => /^[a-z]{2}\.json$/.test(name));
const catalogs = Object.fromEntries(await Promise.all(languageFiles.map(async name => [
  name.slice(0, 2),
  JSON.parse(await readFile(join(i18nDir, name), 'utf8')),
])));

const staticKeys = [...wizard.matchAll(/t\(['"]setup\.([a-z0-9_]+)['"]/g)].map(match => match[1]);
const dynamicKeys = [
  ...['analytical', 'direct', 'supportive', 'strategic'].map(value => `step3_tone_${value}`),
  ...['low', 'medium', 'high'].map(value => `step3_risk_${value}`),
  ...['strict', 'balanced', 'open'].map(value => `step3_security_${value}`),
  ...['ultra_economy', 'economy', 'balanced', 'high_capability', 'premium', 'custom']
    .flatMap(value => [`routing_${value}`, `routing_${value}_desc`]),
];
const requiredKeys = [...new Set([...staticKeys, ...dynamicKeys])].sort();
const placeholders = value => [...String(value).matchAll(/\{[a-z0-9_]+\}/gi)].map(match => match[0]).sort();

for (const [language, catalog] of Object.entries(catalogs)) {
  assert.ok(catalog.setup, `${language} is missing the setup catalog`);
  for (const key of requiredKeys) {
    assert.equal(typeof catalog.setup[key], 'string', `${language} is missing setup.${key}`);
    assert.notEqual(catalog.setup[key].trim(), '', `${language} has an empty setup.${key}`);
    assert.deepEqual(
      placeholders(catalog.setup[key]),
      placeholders(catalogs.en.setup[key]),
      `${language} changed placeholders in setup.${key}`,
    );
  }
}

console.log(`Setup Wizard i18n: ${requiredKeys.length} keys validated across ${languageFiles.length} languages.`);
