"""
Wrap hardcoded strings in Bushido.tsx, Logs.tsx, Chat.tsx, Updates.tsx with t() calls.
"""
import pathlib, re

SRC = pathlib.Path(r'c:\Users\mdper\Documents\Projekter\Shogun\frontend\src\pages')

def wrap_page(filename: str, import_line: str, replacements: list[tuple[str,str]]):
    """Apply a list of (old, new) string replacements to a file."""
    fpath = SRC / filename
    content = fpath.read_text(encoding='utf-8')
    
    # Add useTranslation import if not present
    if 'useTranslation' not in content:
        # Try cn import first, then fall back to adding after last import
        if "import { cn } from '../lib/utils';" in content:
            content = content.replace(
                "import { cn } from '../lib/utils';",
                "import { cn } from '../lib/utils';\nimport { useTranslation } from '../i18n';",
                1
            )
        else:
            # Find last import and add after it
            import re as re2
            last_import = None
            for m in re2.finditer(r'^import .+$', content, re2.MULTILINE):
                last_import = m
            if last_import:
                pos = last_import.end()
                content = content[:pos] + "\nimport { useTranslation } from '../i18n';" + content[pos:]
    
    # Add the t() hook if not present
    if "const { t } = useTranslation();" not in content:
        # For export function style
        if 'export function' in content:
            match = re.search(r'(export function \w+\(\) \{)', content)
            if match:
                content = content.replace(
                    match.group(1),
                    match.group(1) + '\n  const { t } = useTranslation();',
                    1
                )
        # For export const style
        elif 'export const' in content:
            match = re.search(r'(export const \w+ = \(\) => \{)', content)
            if match:
                content = content.replace(
                    match.group(1),
                    match.group(1) + '\n  const { t } = useTranslation();',
                    1
                )
    
    # Apply replacements
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new, 1)
        else:
            print(f"  WARNING: Could not find: {old[:60]}...")
    
    fpath.write_text(content, encoding='utf-8')
    print(f"OK {filename} - {len(replacements)} replacements applied")


# ─── BUSHIDO.TSX ──────────────────────────────────────────────────────────────

wrap_page('Bushido.tsx', "import { useTranslation } from '../i18n';", [
    # Header
    ('>Bushido <span', ">{t('bushido.title')} <span"),
    ('>Reflection Engine</', ">{t('bushido.badge')}</"),
    ('>Monitor and calibrate the autonomous feedback loops that optimize agent precision.</', ">{t('bushido.subtitle')}</"),
    # Engine status
    ("engineOk ? 'Engine Synchronized' : 'Engine Degraded') : 'Connecting...'",
     "engineOk ? t('bushido.engine_synchronized') : t('bushido.engine_degraded')) : t('bushido.connecting')"),
    # Button
    ("reflecting ? 'REFLECTING...' : 'FORCE REFLECTION'",
     "reflecting ? t('bushido.reflecting') : t('bushido.force_reflection')"),
    # Stats cards
    ("label: 'Avg Fit Quality'", "label: t('bushido.avg_fit_quality')"),
    ("label: 'Active Cycles'", "label: t('bushido.active_cycles')"),
    ("label: 'Optimization Delta'", "label: t('bushido.optimization_delta')"),
    ("label: 'Neural Load'", "label: t('bushido.neural_load')"),
    # Calibration section
    ("/> Behavior Calibration", "/> {t('bushido.behavior_calibration')}"),
    (">unsaved</span>", ">{t('bushido.unsaved')}</span>"),
    # Reflection Intensity
    ("/> Reflection Intensity", "/> {t('bushido.reflection_intensity')}"),
    (">Higher intensity increases token consumption but provides far deeper logical validation.</p>",
     ">{t('bushido.reflection_intensity_desc')}</p>"),
    # Memory Consolidation Rate
    ("/> Memory Consolidation Rate", "/> {t('bushido.memory_consolidation_rate')}"),
    ("/ epoch", "/ {t('bushido.epoch')}"),
    (">Frequency of episodic-to-semantic memory transformation cycles.</p>",
     ">{t('bushido.memory_consolidation_desc')}</p>"),
    # Exploration Variance
    ("/> Exploration Variance", "/> {t('bushido.exploration_variance')}"),
    (">Controls how much the agent explores novel approaches vs. sticking to proven patterns.</p>",
     ">{t('bushido.exploration_variance_desc')}</p>"),
    # Buttons
    ("/> Reset To Baseline", "/> {t('bushido.reset_to_baseline')}"),
    ("saving ? 'Saving...' : 'Save Calibration'",
     "saving ? t('bushido.saving') : t('bushido.save_calibration')"),
    # Insight Stream
    ("/> Insight Stream", "/> {t('bushido.insight_stream')}"),
    (">No recommendations yet. Run a Bushido job to generate insights.<",
     ">{t('bushido.no_recommendations')}<"),
    # Formal Verification
    (">Formal Verification</h4>", ">{t('bushido.formal_verification')}</h4>"),
    (">The Bushido engine uses formal verification loops to ensure that all behavioral optimizations remain strictly within the bounds defined in the Kaizen constitution.<",
     ">{t('bushido.formal_verification_desc')}<"),
    # Status messages
    ("text: 'Reflection cycle initiated. Monitor Insight Stream for results.'",
     "text: t('bushido.reflection_initiated')"),
    ("text: 'Failed to trigger reflection.'",
     "text: t('bushido.reflection_failed')"),
    ("text: 'Calibration saved.'",
     "text: t('bushido.calibration_saved')"),
    ("text: 'Failed to save calibration.'",
     "text: t('bushido.calibration_save_failed')"),
    ("text: 'Calibration reset to baseline.'",
     "text: t('bushido.calibration_reset')"),
    ("text: 'Failed to reset calibration.'",
     "text: t('bushido.calibration_reset_failed')"),
])


# ─── LOGS.TSX ─────────────────────────────────────────────────────────────────

wrap_page('Logs.tsx', "import { useTranslation } from '../i18n';", [
    # Header
    ("""            System Logs
            <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">Audit Trail</span>""",
     """            {t('logs.title')}
            <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">{t('logs.badge')}</span>"""),
    (">Real-time telemetry and execution history across the Samurai lattice.</p>",
     ">{t('logs.subtitle')}</p>"),
    # Live/Paused toggle
    ("/> Live", "/> {t('logs.live')}"),
    ("/> Paused", "/> {t('logs.paused')}"),
    # Search placeholder
    ('placeholder="Search events, types..."', 'placeholder={t(\'logs.search_placeholder\')}'),
    # Filter dropdown
    ('>All Levels</option>', '>{t(\'logs.all_levels\')}</option>'),
    ('>Info</option>', '>{t(\'logs.info\')}</option>'),
    ('>Warn</option>', '>{t(\'logs.warn\')}</option>'),
    ('>Error</option>', '>{t(\'logs.error\')}</option>'),
    ('>Critical</option>', '>{t(\'logs.critical\')}</option>'),
    # Legend
    ("""/> Info</span>
            <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-yellow-400" /> Warn</span>
            <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-red-500" /> Error</span>""",
     """/> {t('logs.info')}</span>
            <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-yellow-400" /> {t('logs.warn')}</span>
            <span className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-red-500" /> {t('logs.error')}</span>"""),
    # Loading state
    (">Establishing Uplink...</span>", ">{t('logs.establishing_uplink')}</span>"),
    # Empty state
    ("""              No logs matching your current filters.""", """              {t('logs.no_logs_matching')}"""),
    # Status bar
    ("events</span>", "{t('logs.events')}</span>"),
    # Status bar terminal node
    ("Terminal Node:", "{t('logs.terminal_node')}:"),
    # Clear confirm
    ("'Clear all log entries from the database? This cannot be undone.'",
     "t('logs.clear_confirm')"),
])


# ─── CHAT.TSX ─────────────────────────────────────────────────────────────────

wrap_page('Chat.tsx', "import { useTranslation } from '../i18n';", [
    # WELCOME message - use literal since it's used as a constant comparison key too
    # We'll keep the WELCOME as-is (it's a constant), but translate the displayed strings
    
    # Header
    ("""            Comms{' '}
            <span className="text-xs font-normal text-shogun-subdued bg-shogun-card px-2 py-1 rounded border border-shogun-border tracking-[0.2em] uppercase">
              Interface
            </span>""",
     """            {t('chat.title')}{' '}
            <span className="text-xs font-normal text-shogun-subdued bg-shogun-card px-2 py-1 rounded border border-shogun-border tracking-[0.2em] uppercase">
              {t('chat.badge')}
            </span>"""),
    (">Direct encrypted link to primary Shogun agent.</p>",
     ">{t('chat.subtitle')}</p>"),
    # Clear button title
    ('title="Clear Terminal (saves to history)"',
     'title={t(\'chat.clear_tooltip\')}'),
    # Empty state
    ('>Terminal empty. Waiting for input...</p>',
     '>{t(\'chat.terminal_empty\')}</p>'),
    # Input placeholders
    ("placeholder={isThinking ? 'Transmitting directive...' : 'Enter directive...'}",
     "placeholder={isThinking ? t('chat.placeholder_thinking') : t('chat.placeholder')}"),
    # View History
    ("View History ({history.length} sessions)",
     "{t('chat.view_history')} ({history.length} {t('chat.sessions')})"),
    # Enter to send
    (">Enter to send</span>", ">{t('chat.enter_to_send')}</span>"),
    # Web Search label
    ('{msg.search ? "Web Search" : msg.model}',
     '{msg.search ? t(\'chat.web_search\') : msg.model}'),
    # Error message
    ("Terminal bridge interrupted. Check backend connectivity.",
     "' + t('chat.bridge_interrupted') + '"),
    # History panel
    ("""                   Comms History
                </h3>""",
     """                   {t('chat.comms_history')}
                </h3>"""),
    ("archived session{history.length !== 1 ? 's' : ''} — stored locally",
     "{t('chat.archived_sessions')}"),
    (">No history yet. Clear a session to archive it.</p>",
     ">{t('chat.no_history')}</p>"),
    (""">
                           Restore
                         </button>""",
     """>
                           {t('chat.restore')}
                         </button>"""),
    ("message{msgCount !== 1 ? 's' : ''}", "{t('chat.messages')}"),
    (""">
                   Clear All History
                 </button>""",
     """>
                   {t('chat.clear_all_history')}
                 </button>"""),
])


# ─── UPDATES.TSX ──────────────────────────────────────────────────────────────

wrap_page('Updates.tsx', "import { useTranslation } from '../i18n';", [
    # Need to add the i18n import after the lucide import
    # Header
    ("""          System Updates
        </h1>""",
     """          {t('updates_page.title')}
        </h1>"""),
    (">Keep your Shogun installation up to date.</p>",
     ">{t('updates_page.subtitle')}</p>"),
    # Version card labels
    (">Current Version</p>", ">{t('updates_page.current_version')}</p>"),
    (">Latest Available</p>", ">{t('updates_page.latest_available')}</p>"),
    # Status messages
    (">A new version is available!</span>", ">{t('updates_page.new_version_available')}</span>"),
    (""">You're running the latest version.</span>""", ">{t('updates_page.up_to_date')}</span>"),
    # Changelog
    (">What's new in v{status.remote_version}</h3>",
     ">{t('updates_page.whats_new')} v{status.remote_version}</h3>"),
    (">Released: {", ">{t('updates_page.released')}: {"),
    # Confirm dialog
    ("'This will download and apply the latest version. The frontend will be rebuilt. Continue?'",
     "t('updates_page.install_confirm')"),
    # Buttons
    ("checking ? 'Checking...' : 'Check for Updates'",
     "checking ? t('updates_page.checking') : t('updates_page.check_for_updates')"),
    ("installing ? 'Installing update...' : 'Install Update'",
     "installing ? t('updates_page.installing') : t('updates_page.install_update')"),
    # Last checked
    (">Last checked: {", ">{t('updates_page.last_checked')}: {"),
    # Info section
    (">• Updates are checked automatically every 6 hours.</p>",
     ">{t('updates_page.info_auto_check')}</p>"),
    (">• Updates preserve your data, database, configs, and virtual environment.</p>",
     ">{t('updates_page.info_preserve')}</p>"),
    (">• After installing an update, restart Shogun to apply changes.</p>",
     ">{t('updates_page.info_restart')}</p>"),
])


print("\nAll 4 pages wrapped with t() calls!")
