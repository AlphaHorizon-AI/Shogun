"""Add new profile keys for Models/Permissions/Operations tabs to all i18n files."""
import json
from pathlib import Path

I18N_DIR = Path(__file__).resolve().parent.parent / "frontend" / "src" / "i18n"

# New keys to merge into each language's "profile" section
NEW_KEYS = {
    "da": {
        "primary_model": "Prim\u00e6r Model", "primary_model_desc": "Standardmodellen brugt til al Shogun-r\u00e6sonnering og opgaveeksekvering.",
        "no_providers": "Ingen aktive udbydere fundet.", "configure_katana": "Konfigurer i The Katana \u2192",
        "choose_model": "\u2014 V\u00e6lg en model \u2014", "primary_tag": "PRIM\u00c6R",
        "fallback_models": "Reservemodeller", "fallback_models_desc": "Bruges n\u00e5r den prim\u00e6re er utilg\u00e6ngelig. R\u00e6kkef\u00f8lge er vigtig.",
        "selected": "valgt", "no_providers_short": "Ingen aktive udbydere.",
        "add_fallback_placeholder": "\u2014 Tilf\u00f8j en reservemodel \u2014", "drag_reorder": "Tr\u00e6k for at \u00e6ndre r\u00e6kkef\u00f8lge.",
        "no_fallbacks": "Ingen reserver valgt \u2014 den prim\u00e6re model vil altid blive brugt.",
        "select_routing": "\u2014 V\u00e6lg routing-strategi \u2014",
        "custom": "Tilpasset", "security_risk_index": "Sikkerhedsrisikoindeks",
        "locked_down": "L\u00c5ST NED", "risk_balanced": "BALANCERET", "permissive": "TILLADENDE",
        "base_policy": "Basispolitik", "select_security_tier": "V\u00e6lg sikkerhedsniveau...",
        "custom_policy_name": "Tilpasset Politiknavn",
        "mode_full": "Fuld", "mode_scoped": "Afgr\u00e6nset", "mode_allowlist": "Hvidliste", "mode_disabled": "Deaktiveret",
        "status_active": "Aktiv", "no_tools": "Ingen v\u00e6rkt\u00f8jer eller API'er registreret i Katana Toolbox endnu.",
        "add_custom_website": "Tilf\u00f8j Tilpasset Website",
        "all_websites_warning": "\u26a0 Alle websites tilladt", "all_websites_desc": "\u2014 Agenten kan tilg\u00e5 ethvert dom\u00e6ne uden begr\u00e6nsning.",
        "select_policy_prompt": "V\u00e6lg en politik for at se og tilpasse begr\u00e6nsninger.",
        "reset_to_preset": "Nulstil til Standard", "skill_inventory": "F\u00e6rdighedsoversigt",
        "browse_dojo": "Gennemse Dojo for F\u00e6rdigheder",
        "system_diagnostics": "Systemdiagnostik", "vector_engine": "Vektormotor (Qdrant)",
        "lattice_sync": "Gitter Synkroniseret", "offline_error": "Offline / Diskfejl",
        "relational_core": "Relationel Kerne", "sqlite_optimal": "SQLite Ydelse: Optimal",
        "healthy": "Sund", "lattice_sync_title": "Gittersynkronisering",
        "lattice_sync_desc": "Vektorindekser synkroniseres automatisk hvert 15. minut.",
        "last_sync": "Sidste vellykkede synkronisering skete for", "minutes_ago": "minutter siden.",
        "operational_cadence": "Operationel Kadence (Cron)",
        "running": "K\u00f8rer\u2026", "run_now": "K\u00f8r Nu",
        "status_active_label": "Aktiv", "status_paused": "Sat p\u00e5 pause",
        "create_custom_job": "Opret Tilpasset Job", "builder": "Bygger",
        "job_name": "Jobnavn", "job_type": "Jobtype", "frequency": "Frekvens",
        "priority": "Prioritet", "priority_low": "Lav", "priority_normal": "Normal",
        "priority_high": "H\u00f8j", "priority_critical": "Kritisk",
        "options": "Indstillinger", "include_samurai": "Inkluder Samurai-metrikker",
        "include_samurai_desc": "Medtag underagentdata i revisionen",
        "dry_run": "Pr\u00f8vek\u00f8rsel (kun forh\u00e5ndsvisning)", "auto_approve": "Auto-godkend resultater",
        "task_instruction": "Opgaveinstruktion", "create_schedule_btn": "Opret & Planl\u00e6g Job",
        "active_custom_schedules": "Aktive Tilpassede Planer", "refresh": "Opdater",
    },
    "de": {
        "primary_model": "Prim\u00e4res Modell", "primary_model_desc": "Das Standardmodell f\u00fcr alle Shogun-Argumentation und Aufgabenausf\u00fchrung.",
        "no_providers": "Keine aktiven Anbieter gefunden.", "configure_katana": "In The Katana konfigurieren \u2192",
        "choose_model": "\u2014 Modell w\u00e4hlen \u2014", "primary_tag": "PRIM\u00c4R",
        "fallback_models": "Fallback-Modelle", "fallback_models_desc": "Wird verwendet, wenn das prim\u00e4re nicht verf\u00fcgbar ist. Reihenfolge ist wichtig.",
        "selected": "ausgew\u00e4hlt", "no_providers_short": "Keine aktiven Anbieter.",
        "add_fallback_placeholder": "\u2014 Fallback-Modell hinzuf\u00fcgen \u2014", "drag_reorder": "Ziehen zum Neuordnen.",
        "no_fallbacks": "Keine Fallbacks ausgew\u00e4hlt \u2014 das prim\u00e4re Modell wird immer verwendet.",
        "select_routing": "\u2014 Routing-Strategie w\u00e4hlen \u2014",
        "custom": "Benutzerdefiniert", "security_risk_index": "Sicherheitsrisikoindex",
        "locked_down": "GESPERRT", "risk_balanced": "AUSGEWOGEN", "permissive": "FREIZ\u00dcGIG",
        "base_policy": "Basisrichtlinie", "select_security_tier": "Sicherheitsstufe w\u00e4hlen...",
        "custom_policy_name": "Benutzerdefinierter Richtlinienname",
        "mode_full": "Voll", "mode_scoped": "Begrenzt", "mode_allowlist": "Whitelist", "mode_disabled": "Deaktiviert",
        "status_active": "Aktiv", "no_tools": "Noch keine Tools oder APIs in der Katana Toolbox registriert.",
        "add_custom_website": "Benutzerdefinierte Website hinzuf\u00fcgen",
        "all_websites_warning": "\u26a0 Alle Websites erlaubt", "all_websites_desc": "\u2014 Der Agent kann ohne Einschr\u00e4nkung auf jede Domain zugreifen.",
        "select_policy_prompt": "W\u00e4hlen Sie eine Richtlinie, um Einschr\u00e4nkungen anzuzeigen und anzupassen.",
        "reset_to_preset": "Auf Standard zur\u00fccksetzen", "skill_inventory": "F\u00e4higkeitsinventar",
        "browse_dojo": "Dojo nach F\u00e4higkeiten durchsuchen",
        "system_diagnostics": "Systemdiagnose", "vector_engine": "Vektormotor (Qdrant)",
        "lattice_sync": "Gitter Synchronisiert", "offline_error": "Offline / Festplattenfehler",
        "relational_core": "Relationaler Kern", "sqlite_optimal": "SQLite-Leistung: Optimal",
        "healthy": "Gesund", "lattice_sync_title": "Gitter-Sync",
        "lattice_sync_desc": "Vektorindizes werden automatisch alle 15 Minuten synchronisiert.",
        "last_sync": "Die letzte erfolgreiche Synchronisierung war vor", "minutes_ago": "Minuten.",
        "operational_cadence": "Operativer Rhythmus (Cron)",
        "running": "L\u00e4uft\u2026", "run_now": "Jetzt ausf\u00fchren",
        "status_active_label": "Aktiv", "status_paused": "Pausiert",
        "create_custom_job": "Benutzerdefinierten Job erstellen", "builder": "Builder",
        "job_name": "Jobname", "job_type": "Jobtyp", "frequency": "Frequenz",
        "priority": "Priorit\u00e4t", "priority_low": "Niedrig", "priority_normal": "Normal",
        "priority_high": "Hoch", "priority_critical": "Kritisch",
        "options": "Optionen", "include_samurai": "Samurai-Metriken einbeziehen",
        "include_samurai_desc": "Unteragenten-Daten in die Pr\u00fcfung einbeziehen",
        "dry_run": "Testlauf (nur Vorschau)", "auto_approve": "Ergebnisse auto-genehmigen",
        "task_instruction": "Aufgabenanweisung", "create_schedule_btn": "Job erstellen & planen",
        "active_custom_schedules": "Aktive Benutzerdefinierte Zeitpl\u00e4ne", "refresh": "Aktualisieren",
    },
}

# For languages without full translations, copy English as fallback
en_data = json.loads((I18N_DIR / "en.json").read_text(encoding="utf-8"))
en_new_keys = {k: v for k, v in en_data["profile"].items() if k not in [
    "system_orchestrator","agent_name","active_persona","select_persona","description",
    "autonomy_level","autonomy_desc","select_model","add_fallback","fallback_order",
    "routing_strategy","trait_analytical","trait_direct","trait_supportive","trait_strategic",
    "trait_strict","trait_balanced","trait_open","trait_low","trait_medium","trait_high"
]}

ALL_LANGS = ["da","de","es","fr","it","ja","ko","no","pl","pt","sv","uk","zh"]

for lang in ALL_LANGS:
    fp = I18N_DIR / f"{lang}.json"
    if not fp.exists():
        continue
    data = json.loads(fp.read_text(encoding="utf-8"))
    profile = data.get("profile", {})
    
    if lang in NEW_KEYS:
        profile.update(NEW_KEYS[lang])
    else:
        # Use English fallback for languages not explicitly translated
        for k, v in en_new_keys.items():
            if k not in profile:
                profile[k] = v
    
    data["profile"] = profile
    fp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK {lang}")

print("Done.")
