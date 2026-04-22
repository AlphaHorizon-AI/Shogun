import os
import re
import json
import glob

def find_translations(src_dir):
    pattern = re.compile(r"t\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]((?:\\'|[^'\"])+)['\"]\s*\)")
    
    translations = {}
    
    for root, _, files in os.walk(src_dir):
        for file in files:
            if file.endswith(('.tsx', '.ts')):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    matches = pattern.findall(content)
                    for key, val in matches:
                        # Unescape single quotes
                        val = val.replace("\\'", "'")
                        translations[key] = val
    return translations

def update_json(file_path, new_translations):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        data = {}

    def set_deep(obj, key_path, val):
        parts = key_path.split('.')
        for i, p in enumerate(parts):
            if i == len(parts) - 1:
                if p not in obj:
                    obj[p] = val
            else:
                if p not in obj or not isinstance(obj[p], dict):
                    obj[p] = {}
                obj = obj[p]

    changed = False
    for k, v in new_translations.items():
        # Only populate if missing, so we don't overwrite if somebody actually translated it!
        # Actually, let's just populate missing keys
        parts = k.split('.')
        curr = data
        missing = False
        for i, p in enumerate(parts):
            if i == len(parts) - 1:
                if p not in curr:
                    curr[p] = v
                    changed = True
            else:
                if p not in curr or not isinstance(curr[p], dict):
                    curr[p] = {}
                    changed = True
                curr = curr[p]

    if changed:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    src_dir = r"c:\Users\mdper\Documents\Projekter\Shogun\frontend\src"
    i18n_dir = os.path.join(src_dir, "i18n")
    
    new_translations = find_translations(src_dir)
    print(f"Found {len(new_translations)} translation keys.")
    
    for file in glob.glob(os.path.join(i18n_dir, "*.json")):
        update_json(file, new_translations)
        print(f"Updated {file}")

if __name__ == "__main__":
    main()
