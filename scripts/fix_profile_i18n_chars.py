"""Fix Danish profile translations to use proper special characters."""
import json
from pathlib import Path

I18N_DIR = Path(__file__).resolve().parent.parent / "frontend" / "src" / "i18n"

# Danish fixes with proper characters
da_profile = {
    "system_orchestrator": "Systemorkestrator",
    "agent_name": "Agentnavn",
    "active_persona": "Aktiv Persona",
    "select_persona": "V\u00e6lg en persona...",
    "description": "Beskrivelse",
    "autonomy_level": "Autonominiveau",
    "autonomy_desc": "H\u00f8jere niveauer tillader Shogun at oprette underagenter og udf\u00f8re komplekse v\u00e6rkt\u00f8jer uden eksplicit operat\u00f8rbekr\u00e6ftelse.",
    "select_model": "V\u00e6lg Model",
    "add_fallback": "Tilf\u00f8j Reserve",
    "fallback_order": "Reserver\u00e6kkef\u00f8lge",
    "routing_strategy": "Routing Strategi",
    "trait_analytical": "Analytisk",
    "trait_direct": "Direkte",
    "trait_supportive": "St\u00f8ttende",
    "trait_strategic": "Strategisk",
    "trait_strict": "Streng",
    "trait_balanced": "Balanceret",
    "trait_open": "\u00c5ben",
    "trait_low": "Lav",
    "trait_medium": "Middel",
    "trait_high": "H\u00f8j",
}

# German fixes
de_profile = {
    "system_orchestrator": "Systemorchestrator",
    "agent_name": "Agentenname",
    "active_persona": "Aktive Persona",
    "select_persona": "Persona ausw\u00e4hlen...",
    "description": "Beschreibung",
    "autonomy_level": "Autonomiestufe",
    "autonomy_desc": "H\u00f6here Stufen erlauben Shogun, Unteragenten zu erstellen und komplexe Werkzeuge ohne explizite Operatorbest\u00e4tigung auszuf\u00fchren.",
    "select_model": "Modell ausw\u00e4hlen",
    "add_fallback": "Fallback hinzuf\u00fcgen",
    "fallback_order": "Fallback-Reihenfolge",
    "routing_strategy": "Routing-Strategie",
    "trait_analytical": "Analytisch",
    "trait_direct": "Direkt",
    "trait_supportive": "Unterst\u00fctzend",
    "trait_strategic": "Strategisch",
    "trait_strict": "Streng",
    "trait_balanced": "Ausgewogen",
    "trait_open": "Offen",
    "trait_low": "Niedrig",
    "trait_medium": "Mittel",
    "trait_high": "Hoch",
}

# Spanish fixes
es_profile = {
    "system_orchestrator": "Orquestador del Sistema",
    "agent_name": "Nombre del Agente",
    "active_persona": "Persona Activa",
    "select_persona": "Seleccionar una persona...",
    "description": "Descripci\u00f3n",
    "autonomy_level": "Nivel de Autonom\u00eda",
    "autonomy_desc": "Niveles m\u00e1s altos permiten a Shogun crear subagentes y ejecutar herramientas complejas sin confirmaci\u00f3n expl\u00edcita del operador.",
    "select_model": "Seleccionar Modelo",
    "add_fallback": "Agregar Respaldo",
    "fallback_order": "Orden de Respaldo",
    "routing_strategy": "Estrategia de Enrutamiento",
    "trait_analytical": "Anal\u00edtico",
    "trait_direct": "Directo",
    "trait_supportive": "De apoyo",
    "trait_strategic": "Estrat\u00e9gico",
    "trait_strict": "Estricto",
    "trait_balanced": "Equilibrado",
    "trait_open": "Abierto",
    "trait_low": "Bajo",
    "trait_medium": "Medio",
    "trait_high": "Alto",
}

# French fixes
fr_profile = {
    "system_orchestrator": "Orchestrateur Syst\u00e8me",
    "agent_name": "Nom de l'Agent",
    "active_persona": "Persona Active",
    "select_persona": "Choisir une persona...",
    "description": "Description",
    "autonomy_level": "Niveau d'Autonomie",
    "autonomy_desc": "Des niveaux plus \u00e9lev\u00e9s permettent \u00e0 Shogun de cr\u00e9er des sous-agents et d'ex\u00e9cuter des outils complexes sans confirmation explicite de l'op\u00e9rateur.",
    "select_model": "Choisir un Mod\u00e8le",
    "add_fallback": "Ajouter un Repli",
    "fallback_order": "Ordre de Repli",
    "routing_strategy": "Strat\u00e9gie de Routage",
    "trait_analytical": "Analytique",
    "trait_direct": "Direct",
    "trait_supportive": "Bienveillant",
    "trait_strategic": "Strat\u00e9gique",
    "trait_strict": "Strict",
    "trait_balanced": "\u00c9quilibr\u00e9",
    "trait_open": "Ouvert",
    "trait_low": "Faible",
    "trait_medium": "Moyen",
    "trait_high": "\u00c9lev\u00e9",
}

# Italian fixes  
it_profile = {
    "system_orchestrator": "Orchestratore di Sistema",
    "agent_name": "Nome Agente",
    "active_persona": "Persona Attiva",
    "select_persona": "Seleziona una persona...",
    "description": "Descrizione",
    "autonomy_level": "Livello di Autonomia",
    "autonomy_desc": "Livelli pi\u00f9 alti consentono a Shogun di creare sotto-agenti ed eseguire strumenti complessi senza conferma esplicita dell'operatore.",
    "select_model": "Seleziona Modello",
    "add_fallback": "Aggiungi Riserva",
    "fallback_order": "Ordine di Riserva",
    "routing_strategy": "Strategia di Routing",
    "trait_analytical": "Analitico",
    "trait_direct": "Diretto",
    "trait_supportive": "Di supporto",
    "trait_strategic": "Strategico",
    "trait_strict": "Rigoroso",
    "trait_balanced": "Bilanciato",
    "trait_open": "Aperto",
    "trait_low": "Basso",
    "trait_medium": "Medio",
    "trait_high": "Alto",
}

# Norwegian fixes
no_profile = {
    "system_orchestrator": "Systemorkestrator",
    "agent_name": "Agentnavn",
    "active_persona": "Aktiv Persona",
    "select_persona": "Velg en persona...",
    "description": "Beskrivelse",
    "autonomy_level": "Autonominiv\u00e5",
    "autonomy_desc": "H\u00f8yere niv\u00e5er lar Shogun opprette underagenter og utf\u00f8re komplekse verkt\u00f8y uten eksplisitt operat\u00f8rbekreftelse.",
    "select_model": "Velg Modell",
    "add_fallback": "Legg til Reserve",
    "fallback_order": "Reserverekkefl\u00f8ge",
    "routing_strategy": "Rutingstrategi",
    "trait_analytical": "Analytisk",
    "trait_direct": "Direkte",
    "trait_supportive": "St\u00f8ttende",
    "trait_strategic": "Strategisk",
    "trait_strict": "Streng",
    "trait_balanced": "Balansert",
    "trait_open": "\u00c5pen",
    "trait_low": "Lav",
    "trait_medium": "Middels",
    "trait_high": "H\u00f8y",
}

# Polish fixes
pl_profile = {
    "system_orchestrator": "Orkiestrator Systemu",
    "agent_name": "Nazwa Agenta",
    "active_persona": "Aktywna Persona",
    "select_persona": "Wybierz person\u0119...",
    "description": "Opis",
    "autonomy_level": "Poziom Autonomii",
    "autonomy_desc": "Wy\u017csze poziomy pozwalaj\u0105 Shogunowi tworzy\u0107 podagent\u00f3w i wykonywa\u0107 z\u0142o\u017cone narz\u0119dzia bez jawnego potwierdzenia operatora.",
    "select_model": "Wybierz Model",
    "add_fallback": "Dodaj Rezerwowy",
    "fallback_order": "Kolejno\u015b\u0107 Rezerwowa",
    "routing_strategy": "Strategia Routingu",
    "trait_analytical": "Analityczny",
    "trait_direct": "Bezpo\u015bredni",
    "trait_supportive": "Wspieraj\u0105cy",
    "trait_strategic": "Strategiczny",
    "trait_strict": "\u015aci\u015b\u0142y",
    "trait_balanced": "Zr\u00f3wnowa\u017cony",
    "trait_open": "Otwarty",
    "trait_low": "Niski",
    "trait_medium": "\u015aredni",
    "trait_high": "Wysoki",
}

# Portuguese fixes
pt_profile = {
    "system_orchestrator": "Orquestrador de Sistema",
    "agent_name": "Nome do Agente",
    "active_persona": "Persona Ativa",
    "select_persona": "Selecionar uma persona...",
    "description": "Descri\u00e7\u00e3o",
    "autonomy_level": "N\u00edvel de Autonomia",
    "autonomy_desc": "N\u00edveis mais altos permitem que o Shogun crie subagentes e execute ferramentas complexas sem confirma\u00e7\u00e3o expl\u00edcita do operador.",
    "select_model": "Selecionar Modelo",
    "add_fallback": "Adicionar Reserva",
    "fallback_order": "Ordem de Reserva",
    "routing_strategy": "Estrat\u00e9gia de Roteamento",
    "trait_analytical": "Anal\u00edtico",
    "trait_direct": "Direto",
    "trait_supportive": "De apoio",
    "trait_strategic": "Estrat\u00e9gico",
    "trait_strict": "Rigoroso",
    "trait_balanced": "Equilibrado",
    "trait_open": "Aberto",
    "trait_low": "Baixo",
    "trait_medium": "M\u00e9dio",
    "trait_high": "Alto",
}

# Swedish fixes
sv_profile = {
    "system_orchestrator": "Systemorkestrator",
    "agent_name": "Agentnamn",
    "active_persona": "Aktiv Persona",
    "select_persona": "V\u00e4lj en persona...",
    "description": "Beskrivning",
    "autonomy_level": "Autonominiv\u00e5",
    "autonomy_desc": "H\u00f6gre niv\u00e5er till\u00e5ter Shogun att skapa underagenter och utf\u00f6ra komplexa verktyg utan uttrycklig operat\u00f6rsbekr\u00e4ftelse.",
    "select_model": "V\u00e4lj Modell",
    "add_fallback": "L\u00e4gg till Reserv",
    "fallback_order": "Reservordning",
    "routing_strategy": "Routingstrategi",
    "trait_analytical": "Analytisk",
    "trait_direct": "Direkt",
    "trait_supportive": "St\u00f6djande",
    "trait_strategic": "Strategisk",
    "trait_strict": "Strikt",
    "trait_balanced": "Balanserad",
    "trait_open": "\u00d6ppen",
    "trait_low": "L\u00e5g",
    "trait_medium": "Medel",
    "trait_high": "H\u00f6g",
}

FIXES = {
    "da": da_profile,
    "de": de_profile,
    "es": es_profile,
    "fr": fr_profile,
    "it": it_profile,
    "no": no_profile,
    "pl": pl_profile,
    "pt": pt_profile,
    "sv": sv_profile,
}

for lang, profile_data in FIXES.items():
    fp = I18N_DIR / f"{lang}.json"
    data = json.loads(fp.read_text(encoding="utf-8"))
    data["profile"] = profile_data
    fp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK {lang}: fixed special characters")

print("\nDone.")
