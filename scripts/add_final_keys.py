"""Add final missing keys to en.json and propagate."""
import json, pathlib

I18N = pathlib.Path(r'c:\Users\mdper\Documents\Projekter\Shogun\frontend\src\i18n')

EXTRA_KATANA = {
    "get_token_from": "Get a token from",
    "routing_legend_wins": "wins",
    "routing_legend_wildcard": "Use",
    "routing_legend_catch": "as the last rule to catch all unmatched tasks",
    "auto_whitelist_desc": "It will automatically test and whitelist your ID.",
}

EXTRA_DA = {
    "get_token_from": "Hent et token fra",
    "routing_legend_wins": "vinder",
    "routing_legend_wildcard": "Brug",
    "routing_legend_catch": "som den sidste regel for at fange alle umatchede opgaver",
    "auto_whitelist_desc": "Den vil automatisk teste og hvidliste dit ID.",
}

TRANSLATIONS = {
    "da": EXTRA_DA,
    "de": {
        "get_token_from": "Holen Sie ein Token von",
        "routing_legend_wins": "gewinnt",
        "routing_legend_wildcard": "Verwende",
        "routing_legend_catch": "als letzte Regel, um alle nicht zugeordneten Aufgaben abzufangen",
        "auto_whitelist_desc": "Es wird automatisch testen und Ihre ID auf die Whitelist setzen.",
    },
    "es": {
        "get_token_from": "Obtener un token de",
        "routing_legend_wins": "gana",
        "routing_legend_wildcard": "Usa",
        "routing_legend_catch": "como última regla para capturar todas las tareas no coincidentes",
        "auto_whitelist_desc": "Probará automáticamente y añadirá tu ID a la lista blanca.",
    },
    "fr": {
        "get_token_from": "Obtenez un jeton de",
        "routing_legend_wins": "gagne",
        "routing_legend_wildcard": "Utilisez",
        "routing_legend_catch": "comme dernière règle pour capturer toutes les tâches non correspondantes",
        "auto_whitelist_desc": "Il testera et ajoutera automatiquement votre ID à la liste blanche.",
    },
}

for lang_file in sorted(I18N.glob('*.json')):
    lang = lang_file.stem
    data = json.loads(lang_file.read_text(encoding='utf-8'))
    
    if 'katana' not in data:
        data['katana'] = {}
    
    if lang == 'en':
        data['katana'].update(EXTRA_KATANA)
    elif lang in TRANSLATIONS:
        data['katana'].update(TRANSLATIONS[lang])
    else:
        # Use English as fallback
        data['katana'].update(EXTRA_KATANA)
    
    lang_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"OK {lang}.json")

print("Done!")
