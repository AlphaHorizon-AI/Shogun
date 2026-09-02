import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const catalogDir = path.resolve(here, '../src/i18n/templates');
const languages = ['en', 'da', 'de', 'es', 'fr', 'hi', 'it', 'ja', 'ko', 'no', 'pl', 'pt', 'sv', 'uk', 'zh'];
const requiredSections = ['ui', 'categories', 'difficulty', 'agentFlow'];
const english = JSON.parse(fs.readFileSync(path.join(catalogDir, 'en.json'), 'utf8'));
const failures = [];

for (const language of languages) {
  const filename = path.join(catalogDir, `${language}.json`);
  if (!fs.existsSync(filename)) {
    failures.push(`${language}: missing catalog`);
    continue;
  }
  const catalog = JSON.parse(fs.readFileSync(filename, 'utf8'));
  for (const section of requiredSections) {
    if (!catalog[section] || typeof catalog[section] !== 'object') {
      failures.push(`${language}: missing ${section}`);
    }
  }
  for (const section of requiredSections) {
    const expectedKeys = Object.keys(english[section] || {}).sort();
    const actualKeys = Object.keys(catalog[section] || {}).sort();
    if (JSON.stringify(actualKeys) !== JSON.stringify(expectedKeys)) {
      failures.push(`${language}: ${section} keys differ from English`);
    }
  }
  for (const [id, item] of Object.entries(catalog.agentFlow || {})) {
    if (!item.name?.trim() || !item.description?.trim()) {
      failures.push(`${language}: incomplete AgentFlow template ${id}`);
    }
    if (language !== 'en' && !id.startsWith('coding-') && item.description === english.agentFlow[id]?.description) {
      failures.push(`${language}: untranslated AgentFlow description ${id}`);
    }
  }
}

if (Object.keys(english.agentFlow).length !== 173) failures.push('English AgentFlow catalog must contain 173 templates');

if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log(`Template i18n verified: ${languages.length} languages, 173 AgentFlows.`);
