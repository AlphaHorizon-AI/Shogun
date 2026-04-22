import json
import os

translations = {
    "en": "AI Model Provider",
    "da": "AI-modeludbyder",
    "de": "KI-Modellanbieter",
    "it": "Fornitore di Modelli IA",
    "fr": "Fournisseur de Modèles IA",
    "es": "Proveedor de Modelos de IA",
    "pt": "Provedor de Modelos de IA",
    "pl": "Dostawca Modeli AI",
    "no": "AI-modellleverandør",
    "sv": "AI-modellleverantör",
    "uk": "Постачальник моделей ШІ",
    "zh": "AI模型提供商",
    "ja": "AIモデルプロバイダー",
    "ko": "AI 모델 제공자"
}

i18n_dir = r"c:\Users\mdper\Documents\Projekter\Shogun\frontend\src\i18n"

for lang, translation in translations.items():
    file_path = os.path.join(i18n_dir, f"{lang}.json")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if "katana" not in data:
            data["katana"] = {}
            
        data["katana"]["tab_cloud"] = translation
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
print("Language files updated successfully.")

