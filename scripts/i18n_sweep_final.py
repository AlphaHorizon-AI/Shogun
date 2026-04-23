"""
Final i18n sweep: SamuraiNetwork.tsx, Torii.tsx, and complete German translations.
"""
import json, pathlib

SRC   = pathlib.Path(r'c:\Users\mdper\Documents\Projekter\Shogun\frontend\src\pages')
I18N  = pathlib.Path(r'c:\Users\mdper\Documents\Projekter\Shogun\frontend\src\i18n')

def fix(filename, replacements):
    f = SRC / filename
    content = f.read_text(encoding='utf-8')
    applied = skipped = 0
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new, 1)
            applied += 1
        else:
            skipped += 1
            print(f"  SKIP ({filename}): {ascii(old[:60])}")
    f.write_text(content, encoding='utf-8')
    print(f"  => {filename}: {applied} applied, {skipped} skipped")

# ═══════════════════════════════════════════════════════════
# 1. SAMURAI NETWORK
# ═══════════════════════════════════════════════════════════
print("=== SamuraiNetwork.tsx ===")
fix('SamuraiNetwork.tsx', [
    # Header
    (">Fleet Status</span>", ">{t('samurai_network.fleet_status')}</span>"),
    # Search
    ('placeholder="Filter by name or slug..."', "placeholder={t('samurai_network.filter_placeholder')}"),
    (">All Status</option>", ">{t('samurai_network.all_status')}</option>"),
    (">Active</option>", ">{t('samurai_network.status_active')}</option>"),
    (">Suspended</option>", ">{t('samurai_network.status_suspended')}</option>"),
    # Loading
    (">Scanning Grid...</span>", ">{t('samurai_network.scanning_grid')}</span>"),
    # Empty
    (">No active Samurai found in this sector.</td>", ">{t('samurai_network.no_samurai')}</td>"),
    # Idle
    (">Idle \u2014 No active task</span>", ">{t('samurai_network.idle')}</span>"),
    # Routing fallback
    ('>Default</span>\n', ">{t('samurai_network.default_routing')}</span>\n"),
    # Tooltips
    ('title="Suspend Agent"', "title={t('samurai_network.suspend_agent')}"),
    ('title="Resume Agent"', "title={t('samurai_network.resume_agent')}"),
    ('title="Delete Agent"', "title={t('samurai_network.delete_agent')}"),
    ('title="Configure Samurai"', "title={t('samurai_network.configure_samurai')}"),
    # Confirm delete
    ("'Are you sure you want to delete this samurai?'", "t('samurai_network.confirm_delete')"),
    # Edit modal
    (">Configure Samurai</h3>", ">{t('samurai_network.configure_samurai')}</h3>"),
    (">Unit Name</label>", ">{t('samurai_network.unit_name')}</label>"),
    (">Designation (Role)</label>", ">{t('samurai_network.designation_role')}</label>"),
    (">\u2014 Keep current role \u2014</option>", ">{t('samurai_network.keep_current_role')}</option>"),
    (">Current: <span", ">{t('samurai_network.current')}: <span"),
    # Routing Profile label (edit modal)
    ("</Zap> Routing Profile\n", "</Zap> {t('samurai_network.routing_profile')}\n"),
    (">\u2014 System Default \u2014</option>", ">{t('samurai_network.system_default')}</option>"),
    (">Spawn Policy</label>", ">{t('samurai_network.spawn_policy')}</label>"),
    (">Manual Deploy</option>", ">{t('samurai_network.manual_deploy')}</option>"),
    (">Auto-Spawn (Reactive)</option>", ">{t('samurai_network.auto_spawn')}</option>"),
    (">Scheduled Routine</option>", ">{t('samurai_network.scheduled_routine')}</option>"),
    (">Operational Directive</label>", ">{t('samurai_network.operational_directive')}</label>"),
    ('placeholder="Operational role description..."', "placeholder={t('samurai_network.directive_placeholder')}"),
    # Edit modal footer
    ("\n                CANCEL\n", "\n                {t('common.cancel')}\n"),
    ("editSaving ? 'SAVING...' : 'SAVE CHANGES'", "editSaving ? t('samurai_network.saving') : t('samurai_network.save_changes')"),
    ("'Failed to save changes.'", "t('samurai_network.save_failed')"),
    # Deploy modal
    (">Deploy New Samurai</h3>", ">{t('samurai_network.deploy_new')}</h3>"),
    (">Initialize fleet expansion</p>", ">{t('samurai_network.initialize_fleet')}</p>"),
    (">Samurai Designation (Role)</label>", ">{t('samurai_network.samurai_designation')}</label>"),
    (">Select a role...</option>", ">{t('samurai_network.select_role')}</option>"),
    (">Custom Unit Name</label>", ">{t('samurai_network.custom_unit_name')}</label>"),
    # Deploy modal routing
    ("</Zap> Model Routing Profile\n", "</Zap> {t('samurai_network.model_routing_profile')}\n"),
    (">Controls which AI model this samurai uses for inference and task routing.</p>",
     ">{t('samurai_network.routing_description')}</p>"),
    ('placeholder="Select a designation to auto-populate this..."', "placeholder={t('samurai_network.auto_populate_placeholder')}"),
    # Deploy modal footer
    ("\n                  ABORT\n", "\n                  {t('samurai_network.abort')}\n"),
    ("\n                  DEPLOY SAMURAI\n", "\n                  {t('samurai_network.deploy_samurai_btn')}\n"),
    # Second instance of "Current: "
    (">Current: <span className=\"text-shogun-gold", ">{t('samurai_network.current')}: <span className=\"text-shogun-gold"),
    # Second System Default and spawn policy options (deploy modal)
    (">\u2014 System Default \u2014</option>", ">{t('samurai_network.system_default')}</option>"),
    (">Manual Deploy</option>", ">{t('samurai_network.manual_deploy')}</option>"),
    (">Auto-Spawn (Reactive)</option>", ">{t('samurai_network.auto_spawn')}</option>"),
    (">Scheduled Routine</option>", ">{t('samurai_network.scheduled_routine')}</option>"),
    (">Spawn Policy</label>", ">{t('samurai_network.spawn_policy')}</label>"),
    (">Operational Directive</label>", ">{t('samurai_network.operational_directive')}</label>"),
])

# ═══════════════════════════════════════════════════════════
# 2. TORII
# ═══════════════════════════════════════════════════════════
print("\n=== Torii.tsx ===")
fix('Torii.tsx', [
    # Header badge
    (">\n              Security Portal\n", ">\n              {t('torii.badge')}\n"),
    # Harakiri button
    ("posture?.kill_switch_active ? 'Reset Harakiri' : 'Harakiri'",
     "posture?.kill_switch_active ? t('torii.reset_harakiri') : t('torii.harakiri')"),
    # Active posture
    ("`Active: ${posture.active_tier.toUpperCase()}`", "t('torii.active_label') + ': ' + posture.active_tier.toUpperCase()"),
    ("'Loading...'", "t('common.loading')"),
    (">Saving\u2026</span>", ">{t('common.saving')}</span>"),
    # Tier descriptions - need to make them translatable via t()
    ("description: 'Zero-trust. Local only. No external tool execution.'",
     "description: t('torii.tier_shrine_desc')"),
    ("description: 'Restricted network. Allowlist tools. Human-in-the-loop.'",
     "description: t('torii.tier_guarded_desc')"),
    ("description: 'Balanced autonomy. Scoped filesystem access.'",
     "description: t('torii.tier_tactical_desc')"),
    ("description: 'High autonomy. Broad network access. Automated spawns.'",
     "description: t('torii.tier_campaign_desc')"),
    ("description: 'Unrestricted execution. Sandbox environments only.'",
     "description: t('torii.tier_ronin_desc')"),
    # Tier badges
    ("badge: 'MAX'", "badge: t('torii.badge_max')"),
    ("badge: 'DEFAULT'", "badge: t('torii.badge_default')"),
    ("badge: 'UNSAFE'", "badge: t('torii.badge_unsafe')"),
    # Current Constraints
    (">Current Constraints</h4>", ">{t('torii.current_constraints')}</h4>"),
    ("label: 'Filesystem'", "label: t('torii.filesystem')"),
    ("label: 'Network'", "label: t('torii.network')"),
    ("label: 'Shell'", "label: t('torii.shell')"),
    ("label: 'Auto-skills'", "label: t('torii.auto_skills')"),
    ("label: 'Max agents'", "label: t('torii.max_agents')"),
    ("posture.shell_enabled ? 'Enabled' : 'Disabled'",
     "posture.shell_enabled ? t('torii.enabled') : t('torii.disabled')"),
    ("posture.skill_auto_install ? 'Allowed' : 'Off'",
     "posture.skill_auto_install ? t('torii.allowed') : t('torii.off')"),
    # Emergency protocols
    ("> EMERGENCY PROTOCOLS", "> {t('torii.emergency_protocols')}"),
    (">Activating RONIN mode or the Kill Switch removes safety gates. Use only inside a fully isolated environment.",
     ">{t('torii.emergency_desc')}"),
    # Policy Registry
    ("/> Policy Registry", "/> {t('torii.policy_registry')}"),
    ('placeholder="Filter policies..."', "placeholder={t('torii.filter_policies')}"),
    (">Auditing Shields...</span>", ">{t('torii.auditing_shields')}</span>"),
    # Empty states
    ("? `No policies match \"${search}\".`", "? t('torii.no_match')"),
    (": 'No policies defined. Create one below.'", ": t('torii.no_policies')"),
    # Built-in badge
    (">Built-in</span>", ">{t('torii.built_in')}</span>"),
    # Permission blocks
    ("{ruleCount} permission {ruleCount === 1 ? 'block' : 'blocks'}",
     "{ruleCount} {ruleCount === 1 ? t('torii.permission_block') : t('torii.permission_blocks')}"),
    ("> kill-switch\n", "> {t('torii.kill_switch_label')}\n"),
    # Tooltips
    ('title="View policy"', "title={t('torii.view_policy')}"),
    ('title="Export / copy as JSON"', "title={t('torii.export_json')}"),
    ('title="Delete policy"', "title={t('torii.delete_policy_tooltip')}"),
    # Policy count footer
    ("{policies.length} {policies.length === 1 ? 'policy' : 'policies'} in registry",
     "{policies.length} {policies.length === 1 ? t('torii.policy_singular') : t('torii.policy_plural')} {t('torii.in_registry')}"),
    ("showCreate ? 'Cancel' : 'Create Tactical Policy'",
     "showCreate ? t('common.cancel') : t('torii.create_tactical_policy')"),
    # Create form
    ("> New Tactical Policy", "> {t('torii.new_tactical_policy')}"),
    (">Kill-switch enabled</span>", ">{t('torii.kill_switch_enabled')}</span>"),
    (">Dry-run supported</span>", ">{t('torii.dry_run_supported')}</span>"),
    ("\n                    Save Policy\n", "\n                    {t('torii.save_policy')}\n"),
    (">\n                    Cancel\n                  </button>",
     ">\n                    {t('common.cancel')}\n                  </button>"),
    # View modal
    (">Created ", ">{t('torii.created')} "),
    ("copiedId === viewPolicy.id ? 'Copied!' : 'Export JSON'",
     "copiedId === viewPolicy.id ? t('torii.copied') : t('torii.export_json_btn')"),
    (">Permission Blocks</h4>", ">{t('torii.permission_blocks_title')}</h4>"),
    (">No explicit permissions set \u2014 inherits posture defaults.</p>",
     ">{t('torii.no_permissions')}</p>"),
    ("> Delete this policy", "> {t('torii.delete_this_policy')}"),
    # Confirm messages
    ("`Security posture updated to ${tier.toUpperCase()}.`",
     "t('torii.posture_updated') + ' ' + tier.toUpperCase()"),
    ("'Failed to update posture.'", "t('torii.posture_failed')"),
    ("'Reset the Kill Switch? Posture will be restored to TACTICAL.'",
     "t('torii.reset_confirm')"),
    ("'Kill switch reset. Posture restored to TACTICAL.'",
     "t('torii.reset_success')"),
    ("'Failed to reset kill switch.'", "t('torii.reset_failed')"),
    ("'HARAKIRI INITIATED \u2014 POSTURE LOCKED TO SHRINE.'",
     "t('torii.harakiri_initiated')"),
    ("'Failed to activate Harakiri.'", "t('torii.harakiri_failed')"),
    ("`Policy \"${newPolicy.name}\" created.`",
     "t('torii.policy_created')"),
    ("'Failed to create policy.'", "t('torii.policy_create_failed')"),
    ("`Delete policy \"${name}\"? This cannot be undone.`",
     "t('torii.policy_delete_confirm')"),
    ("`Policy \"${name}\" deleted.`",
     "t('torii.policy_deleted')"),
    ("'Failed to delete policy.'", "t('torii.policy_delete_failed')"),
    # Second Built-in badge (modal)
    (">Built-in</span>", ">{t('torii.built_in')}</span>"),
    # View modal flags
    ("label: 'Kill-switch'", "label: t('torii.kill_switch_label')"),
    ("label: 'Dry-run'", "label: t('torii.dry_run_label')"),
    ("{value ? 'Yes' : 'No'}", "{value ? t('common.yes') : t('common.no')}"),
])

# ═══════════════════════════════════════════════════════════
# 3. ADD ALL KEYS TO EN.JSON + PROPAGATE
# ═══════════════════════════════════════════════════════════
print("\n=== Updating translation files ===")

SAMURAI_EN = {
    "fleet_status": "Fleet Status",
    "filter_placeholder": "Filter by name or slug...",
    "all_status": "All Status",
    "status_active": "Active",
    "status_suspended": "Suspended",
    "scanning_grid": "Scanning Grid...",
    "no_samurai": "No active Samurai found in this sector.",
    "idle": "Idle \u2014 No active task",
    "default_routing": "Default",
    "suspend_agent": "Suspend Agent",
    "resume_agent": "Resume Agent",
    "delete_agent": "Delete Agent",
    "configure_samurai": "Configure Samurai",
    "confirm_delete": "Are you sure you want to delete this samurai?",
    "unit_name": "Unit Name",
    "designation_role": "Designation (Role)",
    "keep_current_role": "\u2014 Keep current role \u2014",
    "current": "Current",
    "routing_profile": "Routing Profile",
    "system_default": "\u2014 System Default \u2014",
    "spawn_policy": "Spawn Policy",
    "manual_deploy": "Manual Deploy",
    "auto_spawn": "Auto-Spawn (Reactive)",
    "scheduled_routine": "Scheduled Routine",
    "operational_directive": "Operational Directive",
    "directive_placeholder": "Operational role description...",
    "saving": "SAVING...",
    "save_changes": "SAVE CHANGES",
    "save_failed": "Failed to save changes.",
    "deploy_new": "Deploy New Samurai",
    "initialize_fleet": "Initialize fleet expansion",
    "samurai_designation": "Samurai Designation (Role)",
    "select_role": "Select a role...",
    "custom_unit_name": "Custom Unit Name",
    "model_routing_profile": "Model Routing Profile",
    "routing_description": "Controls which AI model this samurai uses for inference and task routing.",
    "auto_populate_placeholder": "Select a designation to auto-populate this...",
    "abort": "ABORT",
    "deploy_samurai_btn": "DEPLOY SAMURAI",
}

TORII_EN = {
    "badge": "Security Portal",
    "reset_harakiri": "Reset Harakiri",
    "harakiri": "Harakiri",
    "active_label": "Active",
    "tier_shrine_desc": "Zero-trust. Local only. No external tool execution.",
    "tier_guarded_desc": "Restricted network. Allowlist tools. Human-in-the-loop.",
    "tier_tactical_desc": "Balanced autonomy. Scoped filesystem access.",
    "tier_campaign_desc": "High autonomy. Broad network access. Automated spawns.",
    "tier_ronin_desc": "Unrestricted execution. Sandbox environments only.",
    "badge_max": "MAX",
    "badge_default": "DEFAULT",
    "badge_unsafe": "UNSAFE",
    "current_constraints": "Current Constraints",
    "filesystem": "Filesystem",
    "network": "Network",
    "shell": "Shell",
    "auto_skills": "Auto-skills",
    "max_agents": "Max agents",
    "enabled": "Enabled",
    "disabled": "Disabled",
    "allowed": "Allowed",
    "off": "Off",
    "emergency_protocols": "EMERGENCY PROTOCOLS",
    "emergency_desc": "Activating RONIN mode or the Kill Switch removes safety gates. Use only inside a fully isolated environment.",
    "policy_registry": "Policy Registry",
    "filter_policies": "Filter policies...",
    "auditing_shields": "Auditing Shields...",
    "no_match": "No policies match your search.",
    "no_policies": "No policies defined. Create one below.",
    "built_in": "Built-in",
    "permission_block": "permission block",
    "permission_blocks": "permission blocks",
    "kill_switch_label": "kill-switch",
    "view_policy": "View policy",
    "export_json": "Export / copy as JSON",
    "delete_policy_tooltip": "Delete policy",
    "policy_singular": "policy",
    "policy_plural": "policies",
    "in_registry": "in registry",
    "create_tactical_policy": "Create Tactical Policy",
    "new_tactical_policy": "New Tactical Policy",
    "kill_switch_enabled": "Kill-switch enabled",
    "dry_run_supported": "Dry-run supported",
    "save_policy": "Save Policy",
    "created": "Created",
    "copied": "Copied!",
    "export_json_btn": "Export JSON",
    "permission_blocks_title": "Permission Blocks",
    "no_permissions": "No explicit permissions set \u2014 inherits posture defaults.",
    "delete_this_policy": "Delete this policy",
    "posture_updated": "Security posture updated to",
    "posture_failed": "Failed to update posture.",
    "reset_confirm": "Reset the Kill Switch? Posture will be restored to TACTICAL.",
    "reset_success": "Kill switch reset. Posture restored to TACTICAL.",
    "reset_failed": "Failed to reset kill switch.",
    "harakiri_initiated": "HARAKIRI INITIATED \u2014 POSTURE LOCKED TO SHRINE.",
    "harakiri_failed": "Failed to activate Harakiri.",
    "policy_created": "Policy created successfully.",
    "policy_create_failed": "Failed to create policy.",
    "policy_delete_confirm": "Delete this policy? This cannot be undone.",
    "policy_deleted": "Policy deleted.",
    "policy_delete_failed": "Failed to delete policy.",
    "dry_run_label": "Dry-run",
}

COMMON_EN = {
    "cancel": "Cancel",
    "edit": "Edit",
    "delete": "Delete",
    "save": "Save",
    "loading": "Loading...",
    "saving": "Saving\u2026",
    "yes": "Yes",
    "no": "No",
    "actions": "Actions",
}

# ═══════════════════════════════════════════════════════════
# COMPLETE GERMAN TRANSLATIONS (fixing all Katana + new)
# ═══════════════════════════════════════════════════════════
KATANA_DE_COMPLETE = {
    "badge": "Orchestrierung",
    "provider": "Anbieter",
    "available_models": "Verf\u00fcgbare Modelle",
    "display_name": "Anzeigename",
    "select_pulled_model": "Ein heruntergeladenes Modell ausw\u00e4hlen...",
    "scan_for_local_models": "Nach lokalen Modellen suchen",
    "base_url_label": "Basis-URL",
    "auto": "(Auto)",
    "reset": "\u21a9 Zur\u00fccksetzen",
    "override": "\u270e \u00dcberschreiben",
    "default": "Standard",
    "model_location": "Modell-Speicherort",
    "filesystem_path": "Dateipfad",
    "scan": "Scannen",
    "pull_model": "Modell herunterladen",
    "download_to_ollama": "direkt zu Ollama herunterladen",
    "pulling": "Wird heruntergeladen",
    "repull": "Erneut herunterladen",
    "pull": "Herunterladen",
    "update_provider": "ANBIETER AKTUALISIEREN",
    "initiate_provider": "ANBIETER ERSTELLEN",
    "active_providers": "Aktive Anbieter",
    "querying_model_grid": "Modellraster wird abgefragt...",
    "no_providers": "Keine Modellanbieter konfiguriert. Agenten werden offline sein.",
    "active": "Aktiv",
    "not_configured": "Nicht konfiguriert",
    "default_endpoint": "Standard-Endpunkt",
    "edit_provider": "Anbieter bearbeiten",
    "disable": "Deaktivieren",
    "enable": "Aktivieren",
    "delete_provider": "Anbieter l\u00f6schen",
    "active_count": "aktiv",
    "tool_connectors": "Werkzeug-Konnektoren",
    "register_new_tool": "Neues Werkzeug registrieren",
    "register_tool_connector": "Werkzeug-Konnektor registrieren",
    "quick_pick": "\u26a1 Schnellauswahl",
    "manual": "\u270f Manuell",
    "search_apis": "APIs suchen... (z.B. stripe, weather, openai)",
    "no_apis_match": "Keine APIs entsprechen Ihrer Suche.",
    "find_documentation": "Dokumentation finden",
    "stored_locally": "Lokal in der Konnektor-Konfiguration gespeichert. Wird niemals an Dritte gesendet.",
    "select_api_preview": "W\u00e4hlen Sie eine API aus der Liste, um sie hier anzuzeigen.",
    "endpoint": "Endpunkt",
    "auth": "Auth",
    "type": "Typ",
    "risk": "Risiko",
    "register_connector": "Konnektor registrieren",
    "select_api_first": "\u2190 Zuerst eine API ausw\u00e4hlen",
    "loading_connectors": "Konnektoren werden geladen...",
    "no_tools": "Keine Werkzeug-Konnektoren gefunden. Agenten sind derzeit primitiv.",
    "register_first_tool": "+ Erstes Werkzeug registrieren",
    "remove_connector": "Konnektor entfernen",
    "routing_profiles": "Routing-Profile",
    "profiles_count": "Profile",
    "new_profile": "Neues Profil",
    "new_routing_profile": "Neues Routing-Profil",
    "set_as_default_profile": "Als Standardprofil setzen",
    "create_profile": "Profil erstellen",
    "loading_profiles": "Profile werden geladen...",
    "no_routing_profiles": "Keine Routing-Profile",
    "no_routing_profiles_desc": "Erstellen Sie ein Profil, um zu definieren, wie Aufgaben an bestimmte Modellanbieter weitergeleitet werden.",
    "create_first_profile": "+ Erstes Profil erstellen",
    "no_description": "Keine Beschreibung.",
    "rule": "Regel",
    "rules": "Regeln",
    "set_as_default": "Als Standard setzen",
    "delete_profile": "Profil l\u00f6schen",
    "routing_rules": "Routing-Regeln",
    "add_rule": "Regel hinzuf\u00fcgen",
    "no_rules": "Noch keine Regeln \u2014 alle Anfragen fallen auf das Standardmodell zur\u00fcck.",
    "task_type_label": "Aufgabentyp",
    "all_tasks": "Alle Aufgaben",
    "primary_model": "Prim\u00e4res Modell",
    "unlinked": "Nicht verkn\u00fcpft",
    "latency": "Latenz",
    "cost": "Kosten",
    "edit_routing_rule": "Routing-Regel bearbeiten",
    "new_routing_rule": "Neue Routing-Regel",
    "select_provider": "Anbieter ausw\u00e4hlen...",
    "no_providers_yet": "Noch keine Anbieter konfiguriert",
    "add_provider_first": "\u26a0 Zuerst einen Modellanbieter hinzuf\u00fcgen",
    "all_tasks_wildcard": "* Alle Aufgaben (Wildcard)",
    "task_research": "Forschung & Informationsbeschaffung",
    "task_code": "Code & Technik",
    "task_analysis": "Analyse & Schlussfolgerung",
    "task_creative": "Kreative Generierung",
    "task_summarize": "Zusammenfassung",
    "task_planning": "Planung & Strategie",
    "task_qa": "QA & Verifikation",
    "task_chat": "Chat & Konversation",
    "task_extraction": "Datenextraktion",
    "task_translation": "\u00dcbersetzung",
    "task_vision": "Vision & Multimodal",
    "none_unbiased": "Keine (neutral)",
    "latency_low": "Niedrig \u2014 Geschwindigkeit priorisieren",
    "latency_medium": "Mittel \u2014 Ausgewogen",
    "latency_high": "Hoch \u2014 Latenz f\u00fcr Qualit\u00e4t tolerieren",
    "cost_budget": "Budget \u2014 G\u00fcnstigstes Modell bevorzugen",
    "cost_standard": "Standard \u2014 Kosten/Qualit\u00e4t ausbalancieren",
    "cost_premium": "Premium \u2014 Bestes Modell unabh\u00e4ngig von Kosten",
    "update_rule": "Regel aktualisieren",
    "save_rule": "Regel speichern",
    "select_provider_continue": "\u2190 Anbieter ausw\u00e4hlen um fortzufahren",
    "routing_legend": "Regeln werden von oben nach unten ausgewertet. Der erste passende",
    "routing_legend_wins": "gewinnt",
    "routing_legend_wildcard": "Verwende",
    "routing_legend_catch": "als letzte Regel, um alle nicht zugeordneten Aufgaben abzufangen",
    "api_key_option": "API-Schl\u00fcssel",
    "oauth_option": "OAuth",
    "oauth_token": "OAuth-Token",
    "api_key_label": "API-Schl\u00fcssel",
    "ai_model_providers": "KI-Modellanbieter",
    "local_providers": "Lokale Anbieter",
    "telegram_channel": "Telegram-Kanal",
    "telegram_desc": "Verbinden Sie einen Telegram-Bot, um direkt von Ihrem Handy mit Shogun zu chatten.",
    "connected": "Verbunden",
    "mode": "Modus",
    "disconnect": "Trennen",
    "update_configuration": "Konfiguration aktualisieren",
    "connect_a_bot": "Bot verbinden",
    "bot_token": "Bot-Token *",
    "update_connection": "Verbindung aktualisieren",
    "connect_bot": "Bot verbinden",
    "connecting": "Verbinde\u2026",
    "allowed_chat_ids": "Erlaubte Chat-IDs",
    "optional_whitelist": "optionale Whitelist",
    "chat_ids_help": "Kommagetrennte IDs. Leer lassen, um alle zuzulassen. Negative IDs = Gruppen.",
    "polling_desc": "Shogun pollt Telegram. Einfach, keine \u00f6ffentliche URL erforderlich.",
    "webhook_desc": "Telegram pusht an Ihren Server. Erfordert eine \u00f6ffentliche HTTPS-URL.",
    "polling": "Polling",
    "webhook": "Webhook",
    "test_connection": "Verbindung testen",
    "connect_bot_first": "Zuerst einen Bot verbinden.",
    "sending": "Sende\u2026",
    "send_test": "Test senden",
    "quick_setup": "Schnelleinrichtung",
    "auto_detect_chat_id": "Meine Chat-ID automatisch erkennen",
    "must_complete_step5": "Schritt 5 muss vor dem Klicken abgeschlossen sein.",
    "disconnect_confirm": "Telegram-Bot trennen? Das gespeicherte Token wird entfernt.",
    "connection_failed": "Verbindung fehlgeschlagen.",
    "connect_failed": "Telegram-Bot konnte nicht verbunden werden.",
    "bot_disconnected": "Telegram-Bot getrennt.",
    "disconnect_failed": "Trennung fehlgeschlagen.",
    "tg_step1": "Nachricht an @BotFather auf Telegram senden",
    "tg_step2": "Sende /newbot \u2014 folge den Anweisungen",
    "tg_step3": "Kopiere das Bot-Token, das BotFather dir gibt",
    "tg_step4": "F\u00fcge es oben ein und verbinde",
    "tg_step5": "Sende \u201eHallo\u201c direkt an deinen neuen Shogun-Bot!",
    "get_token_from": "Token erhalten von",
    "auto_whitelist_desc": "Es wird automatisch testen und Ihre ID auf die Whitelist setzen.",
}

SAMURAI_DE = {
    "fleet_status": "Flottenstatus",
    "filter_placeholder": "Nach Name oder Slug filtern...",
    "all_status": "Alle Status",
    "status_active": "Aktiv",
    "status_suspended": "Suspendiert",
    "scanning_grid": "Raster wird gescannt...",
    "no_samurai": "Keine aktiven Samurai in diesem Sektor gefunden.",
    "idle": "Unt\u00e4tig \u2014 Keine aktive Aufgabe",
    "default_routing": "Standard",
    "suspend_agent": "Agent suspendieren",
    "resume_agent": "Agent fortsetzen",
    "delete_agent": "Agent l\u00f6schen",
    "configure_samurai": "Samurai konfigurieren",
    "confirm_delete": "Sind Sie sicher, dass Sie diesen Samurai l\u00f6schen m\u00f6chten?",
    "unit_name": "Einheitsname",
    "designation_role": "Bezeichnung (Rolle)",
    "keep_current_role": "\u2014 Aktuelle Rolle beibehalten \u2014",
    "current": "Aktuell",
    "routing_profile": "Routing-Profil",
    "system_default": "\u2014 System-Standard \u2014",
    "spawn_policy": "Spawn-Richtlinie",
    "manual_deploy": "Manuelles Deployment",
    "auto_spawn": "Auto-Spawn (Reaktiv)",
    "scheduled_routine": "Geplante Routine",
    "operational_directive": "Operative Anweisung",
    "directive_placeholder": "Beschreibung der operativen Rolle...",
    "saving": "WIRD GESPEICHERT...",
    "save_changes": "\u00c4NDERUNGEN SPEICHERN",
    "save_failed": "Speichern fehlgeschlagen.",
    "deploy_new": "Neuen Samurai einsetzen",
    "initialize_fleet": "Flottenerweiterung initialisieren",
    "samurai_designation": "Samurai-Bezeichnung (Rolle)",
    "select_role": "Rolle ausw\u00e4hlen...",
    "custom_unit_name": "Benutzerdefinierter Einheitsname",
    "model_routing_profile": "Modell-Routing-Profil",
    "routing_description": "Steuert, welches KI-Modell dieser Samurai f\u00fcr Inferenz und Aufgaben-Routing verwendet.",
    "auto_populate_placeholder": "W\u00e4hlen Sie eine Bezeichnung, um dies automatisch auszuf\u00fcllen...",
    "abort": "ABBRECHEN",
    "deploy_samurai_btn": "SAMURAI EINSETZEN",
}

TORII_DE = {
    "badge": "Sicherheitsportal",
    "reset_harakiri": "Harakiri zur\u00fccksetzen",
    "harakiri": "Harakiri",
    "active_label": "Aktiv",
    "tier_shrine_desc": "Zero-Trust. Nur lokal. Keine externe Werkzeugausf\u00fchrung.",
    "tier_guarded_desc": "Eingeschr\u00e4nktes Netzwerk. Allowlist-Werkzeuge. Mensch-in-der-Schleife.",
    "tier_tactical_desc": "Ausgewogene Autonomie. Begrenzte Dateisystemzugriffe.",
    "tier_campaign_desc": "Hohe Autonomie. Breiter Netzwerkzugang. Automatisierte Spawns.",
    "tier_ronin_desc": "Uneingeschr\u00e4nkte Ausf\u00fchrung. Nur in Sandbox-Umgebungen.",
    "badge_max": "MAX",
    "badge_default": "STANDARD",
    "badge_unsafe": "UNSICHER",
    "current_constraints": "Aktuelle Einschr\u00e4nkungen",
    "filesystem": "Dateisystem",
    "network": "Netzwerk",
    "shell": "Shell",
    "auto_skills": "Auto-F\u00e4higkeiten",
    "max_agents": "Max. Agenten",
    "enabled": "Aktiviert",
    "disabled": "Deaktiviert",
    "allowed": "Erlaubt",
    "off": "Aus",
    "emergency_protocols": "NOTFALLPROTOKOLLE",
    "emergency_desc": "Aktivierung des RONIN-Modus oder des Kill-Switch entfernt Sicherheitsbarrieren. Nur in einer vollst\u00e4ndig isolierten Umgebung verwenden.",
    "policy_registry": "Richtlinien-Register",
    "filter_policies": "Richtlinien filtern...",
    "auditing_shields": "Schutzschilde werden gepr\u00fcft...",
    "no_match": "Keine Richtlinien entsprechen Ihrer Suche.",
    "no_policies": "Keine Richtlinien definiert. Erstellen Sie eine unten.",
    "built_in": "Integriert",
    "permission_block": "Berechtigungsblock",
    "permission_blocks": "Berechtigungsbl\u00f6cke",
    "kill_switch_label": "Kill-Switch",
    "view_policy": "Richtlinie anzeigen",
    "export_json": "Als JSON exportieren / kopieren",
    "delete_policy_tooltip": "Richtlinie l\u00f6schen",
    "policy_singular": "Richtlinie",
    "policy_plural": "Richtlinien",
    "in_registry": "im Register",
    "create_tactical_policy": "Taktische Richtlinie erstellen",
    "new_tactical_policy": "Neue taktische Richtlinie",
    "kill_switch_enabled": "Kill-Switch aktiviert",
    "dry_run_supported": "Probelauf unterst\u00fctzt",
    "save_policy": "Richtlinie speichern",
    "created": "Erstellt",
    "copied": "Kopiert!",
    "export_json_btn": "JSON exportieren",
    "permission_blocks_title": "Berechtigungsbl\u00f6cke",
    "no_permissions": "Keine expliziten Berechtigungen gesetzt \u2014 erbt Standardeinstellungen.",
    "delete_this_policy": "Diese Richtlinie l\u00f6schen",
    "posture_updated": "Sicherheitsstufe aktualisiert auf",
    "posture_failed": "Sicherheitsstufe konnte nicht aktualisiert werden.",
    "reset_confirm": "Kill-Switch zur\u00fccksetzen? Stufe wird auf TACTICAL zur\u00fcckgesetzt.",
    "reset_success": "Kill-Switch zur\u00fcckgesetzt. Stufe auf TACTICAL wiederhergestellt.",
    "reset_failed": "Kill-Switch konnte nicht zur\u00fcckgesetzt werden.",
    "harakiri_initiated": "HARAKIRI EINGELEITET \u2014 STUFE AUF SHRINE GESPERRT.",
    "harakiri_failed": "Harakiri konnte nicht aktiviert werden.",
    "policy_created": "Richtlinie erfolgreich erstellt.",
    "policy_create_failed": "Richtlinie konnte nicht erstellt werden.",
    "policy_delete_confirm": "Diese Richtlinie l\u00f6schen? Dies kann nicht r\u00fcckg\u00e4ngig gemacht werden.",
    "policy_deleted": "Richtlinie gel\u00f6scht.",
    "policy_delete_failed": "Richtlinie konnte nicht gel\u00f6scht werden.",
    "dry_run_label": "Probelauf",
}

COMMON_DE = {
    "cancel": "Abbrechen",
    "edit": "Bearbeiten",
    "delete": "L\u00f6schen",
    "save": "Speichern",
    "loading": "Laden...",
    "saving": "Speichern\u2026",
    "yes": "Ja",
    "no": "Nein",
    "actions": "Aktionen",
}

# Apply to all language files
for lang_file in sorted(I18N.glob('*.json')):
    lang = lang_file.stem
    data = json.loads(lang_file.read_text(encoding='utf-8'))
    
    for section in ['samurai_network', 'torii', 'common']:
        if section not in data:
            data[section] = {}
    
    if lang == 'en':
        data['samurai_network'].update(SAMURAI_EN)
        data['torii'].update(TORII_EN)
        data['common'].update(COMMON_EN)
    elif lang == 'de':
        data['samurai_network'].update(SAMURAI_DE)
        data['torii'].update(TORII_DE)
        data['common'].update(COMMON_DE)
        # Also fix ALL katana keys for German
        if 'katana' not in data:
            data['katana'] = {}
        data['katana'].update(KATANA_DE_COMPLETE)
    else:
        # Use English as fallback for other languages
        data['samurai_network'].update(SAMURAI_EN)
        data['torii'].update(TORII_EN)
        data['common'].update(COMMON_EN)
    
    lang_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"  OK {lang}.json")

print("\nDone!")
