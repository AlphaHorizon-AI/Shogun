"""Fix remaining hardcoded strings using actual file content matching."""
import pathlib

f = pathlib.Path(r'c:\Users\mdper\Documents\Projekter\Shogun\frontend\src\pages\Katana.tsx')
content = f.read_text(encoding='utf-8')

fixes = [
    # Override button (actual unicode chars)
    ("baseUrlOverride ? '\u21a9 Reset' : '\u270e Override'",
     "baseUrlOverride ? t('katana.reset') : t('katana.override')"),
    
    # Quick Pick / Manual (actual emoji)
    ("m === 'quick' ? '\u26a1 Quick Pick' : '\u270f\ufe0f Manual'",
     "m === 'quick' ? t('katana.quick_pick') : t('katana.manual')"),
    
    # Active count in tools
    (">{tools.length} active",
     ">{tools.length} {t('katana.active_count')}"),
    
    # Profiles count in routing
    (">{routingProfiles.length} profiles",
     ">{routingProfiles.length} {t('katana.profiles_count')}"),
    
    # Find documentation
    (">Find documentation \u2192",
     ">{t('katana.find_documentation')} \u2192"),
    
    # API Key field label
    ("API Key\n                                   <span",
     "{t('katana.api_key')}\n                                   <span"),
    
    # Stored locally
    (">Stored locally in the connector config. Never sent to third parties.\n",
     ">{t('katana.stored_locally')}\n"),
    
    # Select API preview
    (">Select an API from the list to preview it here.</p>",
     ">{t('katana.select_api_preview')}</p>"),
    
    # Select an API first (arrow)
    (">\u2190 Select an API first</p>",
     ">{t('katana.select_api_first')}</p>"),
    
    # Register first tool
    (">+ Register your first tool\n",
     ">{t('katana.register_first_tool')}\n"),
    
    # Routing: Set as default profile (checkbox label)
    ("Set as default profile\n",
     "{t('katana.set_as_default_profile')}\n"),
    
    # Create first profile
    (">+ Create your first profile\n",
     ">{t('katana.create_first_profile')}\n"),
    
    # Default badge in routing profile
    ("                                   Default\n                                 </span>",
     "                                   {t('katana.default')}\n                                 </span>"),
    
    # No description
    (">{profile.description || 'No description.'}",
     ">{profile.description || t('katana.no_description')}"),
    
    # Rules count
    ("{rules.length === 1 ? 'rule' : 'rules'}",
     "{rules.length === 1 ? t('katana.rule') : t('katana.rules')}"),
    
    # No rules yet (em dash)
    ("No rules yet \u2014 all requests fall through to the default model.",
     "{t('katana.no_rules')}"),
    
    # All Tasks
    (">{rule.task_type === '*' ? 'All Tasks' : rule.task_type}",
     ">{rule.task_type === '*' ? t('katana.all_tasks') : rule.task_type}"),
    
    # Latency/Cost bias options (em dashes)
    (">Low \u2014 Prioritise speed</option>", ">{t('katana.latency_low')}</option>"),
    (">Medium \u2014 Balanced</option>", ">{t('katana.latency_medium')}</option>"),
    (">High \u2014 Tolerate latency for quality</option>", ">{t('katana.latency_high')}</option>"),
    (">Budget \u2014 Prefer cheapest model</option>", ">{t('katana.cost_budget')}</option>"),
    (">Standard \u2014 Balance cost/quality</option>", ">{t('katana.cost_standard')}</option>"),
    (">Premium \u2014 Best model regardless of cost</option>", ">{t('katana.cost_premium')}</option>"),
    
    # Select provider to continue (arrow)
    (">\u2190 Select a provider to continue</span>",
     ">{t('katana.select_provider_continue')}</span>"),
    
    # Telegram: Mode label
    (">Mode: <span", ">{t('katana.mode')}: <span"),
    
    # Telegram: Connecting with ellipsis
    ("/> Connecting\u2026</>", "/> {t('katana.connecting')}</>"),
    
    # Telegram: Sending with ellipsis
    ("/> Sending\u2026</>", "/> {t('katana.sending')}</>"),
    
    # Telegram: Auto-Detect My Chat ID
    (">Auto-Detect My Chat ID\n",
     ">{t('katana.auto_detect_chat_id')}\n"),
    
    # Telegram: Must complete Step 5
    (">Must complete Step 5 before clicking.",
     ">{t('katana.must_complete_step5')}"),
    
    # Cancel buttons (the remaining ones that had whitespace issues)
    # We'll handle these by looking for the exact content
    # Routing rules cancel
    ("                                     Cancel\n                                   </button>",
     "                                     {t('common.cancel')}\n                                   </button>"),
    
    # Tool register cancel
    ("                       Cancel\n                     </button>",
     "                       {t('common.cancel')}\n                     </button>"),
    
    # Scan button (remaining)
    (">Scan\n                         </button>",
     ">{t('katana.scan')}\n                         </button>"),
    
    # Second None (unbiased) occurrence for cost bias
    (">None (unbiased)</option>",
     ">{t('katana.none_unbiased')}</option>"),
    
    # Polling / webhook button labels
    ("'polling' ? '\ud83d\udd04 Polling' : '\ud83c\udf10 Webhook'",
     "'polling' ? t('katana.polling') : t('katana.webhook')"),
    
    # Quick setup steps  
    ("{ n: '1', t: 'Message @BotFather on Telegram'",
     "{ n: '1', t: t('katana.tg_step1')"),
    ("{ n: '2', t: 'Send /newbot \\u2014 follow the prompts' }",
     "{ n: '2', t: t('katana.tg_step2') }"),
    ("{ n: '3', t: 'Copy the bot token BotFather gives you' }",
     "{ n: '3', t: t('katana.tg_step3') }"),
    ("{ n: '4', t: 'Paste it above and Connect' }",
     "{ n: '4', t: t('katana.tg_step4') }"),
    ("{ n: '5', t: 'Send \\\"Hello\\\" directly to your new Shogun bot!' }",
     "{ n: '5', t: t('katana.tg_step5') }"),
]

applied = 0
for old, new in fixes:
    if old in content:
        content = content.replace(old, new, 1)
        applied += 1
    else:
        print(f"  SKIP: {ascii(old[:60])}...")

f.write_text(content, encoding='utf-8')
print(f"\nOK Katana.tsx - {applied}/{len(fixes)} final fixes applied")
