import json
import pathlib

I18N_DIR = pathlib.Path(r'c:\Users\mdper\Documents\Projekter\Shogun\frontend\src\i18n')

def deep_merge(source, destination):
    """
    Deep merge source into destination.
    Only adds keys that are missing in destination.
    """
    for key, value in source.items():
        if isinstance(value, dict):
            node = destination.setdefault(key, {})
            deep_merge(value, node)
        else:
            if key not in destination:
                destination[key] = value
    return destination

def sync():
    en_file = I18N_DIR / 'en.json'
    if not en_file.exists():
        print("en.json not found!")
        return

    with open(en_file, 'r', encoding='utf-8') as f:
        en_data = json.load(f)

    for lang_file in I18N_DIR.glob('*.json'):
        if lang_file.name == 'en.json':
            continue
        
        print(f"Syncing {lang_file.name}...")
        with open(lang_file, 'r', encoding='utf-8') as f:
            lang_data = json.load(f)
        
        # We want to ensure all keys from EN exist in the target language.
        # If a key exists in target, we keep its translation.
        # If it's missing, we take the EN value.
        synced_data = deep_merge(en_data, lang_data)
        
        with open(lang_file, 'w', encoding='utf-8') as f:
            json.dump(synced_data, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    sync()
