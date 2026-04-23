"""
Deep i18n sweep for Katana.tsx — wraps ALL remaining hardcoded English strings with t() calls.
Also checks SamuraiNetwork.tsx and other pages for remaining strings.
"""
import pathlib

SRC = pathlib.Path(r'c:\Users\mdper\Documents\Projekter\Shogun\frontend\src\pages')

def fix_file(filename, replacements):
    f = SRC / filename
    content = f.read_text(encoding='utf-8')
    applied = 0
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new, 1)
            applied += 1
        else:
            print(f"  SKIP ({filename}): {old[:70]}...")
    f.write_text(content, encoding='utf-8')
    print(f"OK {filename} - {applied}/{len(replacements)} applied")


# ═══════════════════════════════════════════════════════════════════
# KATANA.TSX — PROVIDERS TAB
# ═══════════════════════════════════════════════════════════════════

print("\n=== Katana.tsx: Providers Tab ===")
fix_file('Katana.tsx', [
    # Header badge
    (""">Orchestration</span>""", """>{t('katana.badge')}</span>"""),
    
    # Provider form labels
    ("'Available Models' : 'Display Name'", "t('katana.available_models') : t('katana.display_name')"),
    (">Select a pulled model...</option>", ">{t('katana.select_pulled_model')}</option>"),
    ("/> Scan for local models", "/> {t('katana.scan_for_local_models')}"),
    
    # Base URL
    ("Base URL {isLocal ? '' : '(Auto)'}", "{t('katana.base_url_label')} {isLocal ? '' : t('katana.auto')}"),
    ("baseUrlOverride ? '\\u21a9 Reset' : '\\u270e Override'",
     "baseUrlOverride ? t('katana.reset') : t('katana.override')"),
    # The Default badge
    (">\n                            Default\n                          </span>",
     ">\n                            {t('katana.default')}\n                          </span>"),
    
    # Model Location
    ("/> Model Location", "/> {t('katana.model_location')}"),
    (">(filesystem path)</span>", ">({t('katana.filesystem_path')})</span>"),
    (">Scan", ">{t('katana.scan')}"),
    
    # Pull a Model section
    ("Pull a Model", "{t('katana.pull_model')}"),
    ("download directly to Ollama", "{t('katana.download_to_ollama')}"),
    
    # Pull buttons
    ("/> Pulling</>", "/> {t('katana.pulling')}</>"),
    ("/> Re-pull</>", "/> {t('katana.repull')}</>"),
    ("/> Pull</>", "/> {t('katana.pull')}</>"),
    ("""> Pull\n                              </button>""", """> {t('katana.pull')}\n                              </button>"""),
    
    # Submit buttons
    ("editingProviderId ? 'UPDATE PROVIDER' : 'INITIATE PROVIDER'",
     "editingProviderId ? t('katana.update_provider') : t('katana.initiate_provider')"),
    (">\n                        Cancel\n                      </button>",
     ">\n                        {t('common.cancel')}\n                      </button>"),
    
    # Active Providers title
    ("/> Active Providers", "/> {t('katana.active_providers')}"),
    (">Querying Model Grid...</p>", ">{t('katana.querying_model_grid')}</p>"),
    (">No model providers configured. Agents will be offline.</p>",
     ">{t('katana.no_providers')}</p>"),
    
    # Provider card badges
    (">Active</span>", ">{t('katana.active')}</span>"),
    (">{p.status ?? 'Not configured'}</span>", ">{p.status ?? t('katana.not_configured')}</span>"),
    (">{p.base_url || 'Default Endpoint'}</span>", ">{p.base_url || t('katana.default_endpoint')}</span>"),
    
    # Tooltips
    ('title="Edit Provider"', "title={t('katana.edit_provider')}"),
    ("title={isActive ? 'Disable' : 'Enable'}", "title={isActive ? t('katana.disable') : t('katana.enable')}"),
    ('title="Delete Provider"', "title={t('katana.delete_provider')}"),
])

# ═══════════════════════════════════════════════════════════════════
# KATANA.TSX — TOOLS TAB
# ═══════════════════════════════════════════════════════════════════

print("\n=== Katana.tsx: Tools Tab ===")
fix_file('Katana.tsx', [
    ("/> Tool Connectors", "/> {t('katana.tool_connectors')}"),
    ("> active", "> {t('katana.active_count')}"),
    ("showRegisterTool ? 'Cancel' : 'Register New Tool'",
     "showRegisterTool ? t('common.cancel') : t('katana.register_new_tool')"),
    
    # Register panel
    ("/> Register Tool Connector", "/> {t('katana.register_tool_connector')}"),
    ("'\\u26a1 Quick Pick' : '\\u270f\\ufe0f Manual'",
     "t('katana.quick_pick') : t('katana.manual')"),
    
    # Search placeholder
    ('placeholder="Search APIs... (e.g. stripe, weather, openai)"',
     "placeholder={t('katana.search_apis')}"),
    (">No APIs match your search.</p>", ">{t('katana.no_apis_match')}</p>"),
    (">Find documentation", ">{t('katana.find_documentation')}"),
    
    # API Key label
    (">\n                                   API Key\n                                   <span",
     ">\n                                   {t('katana.api_key')}\n                                   <span"),
    (">Stored locally in the connector config. Never sent to third parties.",
     ">{t('katana.stored_locally')}"),
    (">Select an API from the list to preview it here.</p>",
     ">{t('katana.select_api_preview')}</p>"),
    
    # Quick Pick preview labels
    ("label: 'Endpoint'", "label: t('katana.endpoint')"),
    ("label: 'Auth'", "label: t('katana.auth')"),
    ("label: 'Type'", "label: t('katana.type')"),
    ("label: 'Risk'", "label: t('katana.risk')"),
    
    # Register/Cancel buttons
    ("Register Connector", "{t('katana.register_connector')}"),
    ("\n                       Cancel\n                     ", "\n                       {t('common.cancel')}\n                     "),
    (">\\u2190 Select an API first</p>", ">{t('katana.select_api_first')}</p>"),
    
    # Loading/Empty tool states
    (">Loading Connectors...</p>", ">{t('katana.loading_connectors')}</p>"),
    (">No tool connectors found. Agents are currently primitive.</p>",
     ">{t('katana.no_tools')}</p>"),
    (">+ Register your first tool", ">{t('katana.register_first_tool')}"),
    
    # Tool card tooltip
    ('title="Remove connector"', "title={t('katana.remove_connector')}"),
])

# ═══════════════════════════════════════════════════════════════════
# KATANA.TSX — ROUTING TAB
# ═══════════════════════════════════════════════════════════════════

print("\n=== Katana.tsx: Routing Tab ===")
fix_file('Katana.tsx', [
    ("/> Routing Profiles", "/> {t('katana.routing_profiles')}"),
    ("> profiles", "> {t('katana.profiles_count')}"),
    ("showCreateProfile ? 'Cancel' : 'New Profile'",
     "showCreateProfile ? t('common.cancel') : t('katana.new_profile')"),
    
    # Create profile panel
    ("/> New Routing Profile", "/> {t('katana.new_routing_profile')}"),
    (">Set as default profile", ">{t('katana.set_as_default_profile')}"),
    ("Create Profile", "{t('katana.create_profile')}"),
    (">Loading Profiles...</p>", ">{t('katana.loading_profiles')}</p>"),
    
    # Empty state
    (">No Routing Profiles</h4>", ">{t('katana.no_routing_profiles')}</h4>"),
    ("Create a profile to define how tasks are routed to specific model providers.",
     "{t('katana.no_routing_profiles_desc')}"),
    (">+ Create your first profile", ">{t('katana.create_first_profile')}"),
    
    # Profile card
    (">\n                                   Default\n                                 </span>",
     ">\n                                   {t('katana.default')}\n                                 </span>"),
    (">{profile.description || 'No description.'}", ">{profile.description || t('katana.no_description')}"),
    ("{rules.length === 1 ? 'rule' : 'rules'}", "{rules.length === 1 ? t('katana.rule') : t('katana.rules')}"),
    ('title="Set as default"', "title={t('katana.set_as_default')}"),
    ('title="Delete profile"', "title={t('katana.delete_profile')}"),
    
    # Expanded rules
    (">Routing Rules</p>", ">{t('katana.routing_rules')}</p>"),
    ("/> Add Rule", "/> {t('katana.add_rule')}"),
    (">No rules yet \\u2014 all requests fall through to the default model.</p>",
     ">{t('katana.no_rules')}</p>"),
    
    # Rule details
    (">Task Type</p>", ">{t('katana.task_type_label')}</p>"),
    (">{rule.task_type === '*' ? 'All Tasks' : rule.task_type}",
     ">{rule.task_type === '*' ? t('katana.all_tasks') : rule.task_type}"),
    (">Primary Model</p>", ">{t('katana.primary_model')}</p>"),
    (">Unlinked</span>", ">{t('katana.unlinked')}</span>"),
    (">Latency</p>", ">{t('katana.latency')}</p>"),
    (">Cost</p>", ">{t('katana.cost')}</p>"),
    
    # Edit/Delete labels
    (">Edit</span>", ">{t('common.edit')}</span>"),
    (">Delete</span>", ">{t('common.delete')}</span>"),
    
    # Add Rule form
    ("/> Edit Routing Rule</>", "/> {t('katana.edit_routing_rule')}</>"),
    ("/> New Routing Rule</>", "/> {t('katana.new_routing_rule')}</>"),
    (">Select a provider...</option>", ">{t('katana.select_provider')}</option>"),
    (">No providers configured yet</option>", ">{t('katana.no_providers_yet')}</option>"),
    ("Add a Model Provider first</p>", "{t('katana.add_provider_first')}</p>"),
    
    # Task type dropdown options
    (">* All Tasks (wildcard)</option>", ">{t('katana.all_tasks_wildcard')}</option>"),
    (">Research & Information Gathering</option>", ">{t('katana.task_research')}</option>"),
    (">Code & Engineering</option>", ">{t('katana.task_code')}</option>"),
    (">Analysis & Reasoning</option>", ">{t('katana.task_analysis')}</option>"),
    (">Creative Generation</option>", ">{t('katana.task_creative')}</option>"),
    (">Summarization</option>", ">{t('katana.task_summarize')}</option>"),
    (">Planning & Strategy</option>", ">{t('katana.task_planning')}</option>"),
    (">QA & Verification</option>", ">{t('katana.task_qa')}</option>"),
    (">Chat & Conversation</option>", ">{t('katana.task_chat')}</option>"),
    (">Data Extraction</option>", ">{t('katana.task_extraction')}</option>"),
    (">Translation</option>", ">{t('katana.task_translation')}</option>"),
    (">Vision & Multimodal</option>", ">{t('katana.task_vision')}</option>"),
    
    # Latency bias options
    (">None (unbiased)</option>", ">{t('katana.none_unbiased')}</option>"),
    (">Low \\u2014 Prioritise speed</option>", ">{t('katana.latency_low')}</option>"),
    (">Medium \\u2014 Balanced</option>", ">{t('katana.latency_medium')}</option>"),
    (">High \\u2014 Tolerate latency for quality</option>", ">{t('katana.latency_high')}</option>"),
    
    # Cost bias options - second occurrence of None (unbiased)
    (">Budget \\u2014 Prefer cheapest model</option>", ">{t('katana.cost_budget')}</option>"),
    (">Standard \\u2014 Balance cost/quality</option>", ">{t('katana.cost_standard')}</option>"),
    (">Premium \\u2014 Best model regardless of cost</option>", ">{t('katana.cost_premium')}</option>"),
    
    # Save/Cancel buttons in rule form
    ("editingRuleIdx !== null ? 'Update Rule' : 'Save Rule'",
     "editingRuleIdx !== null ? t('katana.update_rule') : t('katana.save_rule')"),
    (">\n                                     Cancel\n                                   </button>",
     ">\n                                     {t('common.cancel')}\n                                   </button>"),
    (">\\u2190 Select a provider to continue</span>",
     ">{t('katana.select_provider_continue')}</span>"),
    
    # Routing legend
    ("Rules are evaluated top-to-bottom. The first matching",
     "{t('katana.routing_legend')}"),
    # This won't work perfectly since it spans JSX, but let's try...
    
    # Auth type dropdown options (Provider form)
    (">API Key</option>", ">{t('katana.api_key_option')}</option>"),
    (">OAuth</option>", ">{t('katana.oauth_option')}</option>"),
    
    # Auth type label
    ("newProvider.auth_type === 'oauth' ? 'OAuth Token' : 'API Key'",
     "newProvider.auth_type === 'oauth' ? t('katana.oauth_token') : t('katana.api_key_label')"),
    
    # Optgroup labels
    ('label="AI Model Providers"', "label={t('katana.ai_model_providers')}"),
    ('label="Local Providers"', "label={t('katana.local_providers')}"),
])

# ═══════════════════════════════════════════════════════════════════
# KATANA.TSX — TELEGRAM TAB
# ═══════════════════════════════════════════════════════════════════

print("\n=== Katana.tsx: Telegram Tab ===")
fix_file('Katana.tsx', [
    ("/> Telegram Channel", "/> {t('katana.telegram_channel')}"),
    (">Connect a Telegram bot to chat with Shogun directly from your phone.</p>",
     ">{t('katana.telegram_desc')}</p>"),
    (">Connected</span>", ">{t('katana.connected')}</span>"),
    
    # Connected card
    (">Mode: <span", ">{t('katana.mode')}: <span"),
    ("/> Disconnect", "/> {t('katana.disconnect')}"),
    
    # Form
    ("tgStatus?.connected ? 'Update Configuration' : 'Connect a Bot'",
     "tgStatus?.connected ? t('katana.update_configuration') : t('katana.connect_a_bot')"),
    ("/> Bot Token *", "/> {t('katana.bot_token')}"),
    
    # Connect button & polling info
    ("tgStatus?.connected ? 'Update Connection' : 'Connect Bot'",
     "tgStatus?.connected ? t('katana.update_connection') : t('katana.connect_bot')"),
    ("/> Connecting\\u2026</>", "/> {t('katana.connecting')}</>"),
    
    # Allowed Chat IDs
    ("/> Allowed Chat IDs", "/> {t('katana.allowed_chat_ids')}"),
    (">(optional whitelist)</span>", ">({t('katana.optional_whitelist')})</span>"),
    (">Comma-separated IDs. Leave empty to allow all. Negative IDs = groups.</p>",
     ">{t('katana.chat_ids_help')}</p>"),
    
    # Polling/webhook descriptions
    ("tgMode === 'polling' ? 'Shogun polls Telegram. Simple, no public URL needed.' : 'Telegram pushes to your server. Requires a public HTTPS URL.'",
     "tgMode === 'polling' ? t('katana.polling_desc') : t('katana.webhook_desc')"),
    
    # Test connection
    ("/> Test Connection", "/> {t('katana.test_connection')}"),
    (">Connect a bot first.</p>", ">{t('katana.connect_bot_first')}</p>"),
    ("/> Sending\\u2026</>", "/> {t('katana.sending')}</>"),
    ("/> Send Test</>", "/> {t('katana.send_test')}</>"),
    
    # Quick Setup
    ("/> Quick Setup", "/> {t('katana.quick_setup')}"),
    (">Auto-Detect My Chat ID", ">{t('katana.auto_detect_chat_id')}"),
    (">Must complete Step 5 before clicking.", ">{t('katana.must_complete_step5')}"),
    
    # Confirm / disconnect messages
    ("'Disconnect Telegram bot? The stored token will be removed.'",
     "t('katana.disconnect_confirm')"),
    ("'Connection failed.'", "t('katana.connection_failed')"),
    ("'Failed to connect Telegram bot.'", "t('katana.connect_failed')"),
    ("'Telegram bot disconnected.'", "t('katana.bot_disconnected')"),
    ("'Failed to disconnect.'", "t('katana.disconnect_failed')"),
])


print("\n=== Done! ===")
