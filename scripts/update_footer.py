import json
import os

footer_translations = {
    "da": "Skabt af Alpha Horizon · © 2026",
    "de": "Erstellt von Alpha Horizon · © 2026",
    "es": "Creado por Alpha Horizon · © 2026",
    "fr": "Créé par Alpha Horizon · © 2026",
    "it": "Creato da Alpha Horizon · © 2026",
    "ja": "Created by Alpha Horizon · © 2026",
    "ko": "Created by Alpha Horizon · © 2026",
    "no": "Skapt av Alpha Horizon · © 2026",
    "pl": "Stworzone przez Alpha Horizon · © 2026",
    "pt": "Criado por Alpha Horizon · © 2026",
    "sv": "Skapad av Alpha Horizon · © 2026",
    "uk": "Створено Alpha Horizon · © 2026",
    "zh": "由 Alpha Horizon 创建 · © 2026",
    "en": "Created by Alpha Horizon · © 2026"
}

i18n_dir = r"c:\Users\mdper\Documents\Projekter\Shogun\frontend\src\i18n"

for lang, text in footer_translations.items():
    file_path = os.path.join(i18n_dir, f"{lang}.json")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if "common" in data:
            data["common"]["copyright"] = text
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

print("Footer branding updated in all 14 languages.")
