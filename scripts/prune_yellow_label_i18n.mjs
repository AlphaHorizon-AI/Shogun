import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const localeDirectory = path.join(root, 'frontend', 'src', 'i18n')
const templateDirectory = path.join(localeDirectory, 'templates')

const deleteKeys = (target, keys) => {
  if (!target || typeof target !== 'object') return
  for (const key of keys) delete target[key]
}

for (const filename of fs.readdirSync(localeDirectory).filter(name => name.endsWith('.json'))) {
  const target = path.join(localeDirectory, filename)
  const data = JSON.parse(fs.readFileSync(target, 'utf8'))

  deleteKeys(data, ['logs', 'nexus', 'gensui'])
  deleteKeys(data.nav, [
    'logs', 'logs_sub', 'alliance', 'nexus', 'nexus_sub', 'gensui', 'gensui_sub',
  ])
  deleteKeys(data.setup, [
    'mode_team', 'mode_team_desc', 'team_members', 'team_members_desc',
    'teams_upn', 'teams_object_id', 'team_validation', 'security_team_record',
    'server_mode_ronin_explainer',
  ])
  deleteKeys(data.katana, ['team'])

  fs.writeFileSync(target, `${JSON.stringify(data, null, 2)}\n`)
}

const removedTemplateUiKeys = [
  'flow_stacking', 'flow_stacking_subtitle', 'built_in_stacks', 'stack_builder',
  'stack_templates', 'orchestrator', 'search_stack_templates', 'all_stack_categories',
  'reusable_templates', 'shown', 'phases', 'resumable', 'open_program',
  'building_stack', 'could_not_create_stack',
]

const teamsPhrases = [
  ' and Teams', ' og Teams', ' und Teams', ' y Teams', ' et Teams', ' और टीम्स', ' e Teams',
  ' e Team', 'やTeams', 'とTeams', '와 팀', ' 및 Teams', ' i Zespołów',
  ' i zespoły', ' e Equipes', ' та Команди', ' і команди', '和Teams',
]

for (const filename of fs.readdirSync(templateDirectory).filter(name => name.endsWith('.json'))) {
  const target = path.join(templateDirectory, filename)
  const data = JSON.parse(fs.readFileSync(target, 'utf8'))
  deleteKeys(data, ['flowStack'])
  deleteKeys(data.ui, removedTemplateUiKeys)
  for (const templateId of [
    'incident-triage-channel-alert',
    'adv-intelligence-channel-command',
  ]) {
    const template = data.agentFlow?.[templateId]
    if (!template?.description) continue
    for (const phrase of teamsPhrases) {
      template.description = template.description.replaceAll(phrase, '')
    }
  }
  fs.writeFileSync(target, `${JSON.stringify(data, null, 2)}\n`)
}

console.log('Pruned Yellow Label locale catalogs.')
