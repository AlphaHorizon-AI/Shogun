import json, pathlib

d = pathlib.Path(r'c:\Users\mdper\Documents\Projekter\Shogun\frontend\src\i18n')

def get_keys(obj, prefix=''):
    keys = set()
    for k, v in obj.items():
        full = f'{prefix}.{k}' if prefix else k
        if isinstance(v, dict):
            keys.update(get_keys(v, full))
        else:
            keys.add(full)
    return keys

en = json.loads((d / 'en.json').read_text(encoding='utf-8'))
en_keys = get_keys(en)
print(f'en.json has {len(en_keys)} keys')

for lang in ['da','de','es','fr','it','ja','ko','no','pl','pt','sv','uk','zh']:
    data = json.loads((d / f'{lang}.json').read_text(encoding='utf-8'))
    lang_keys = get_keys(data)
    missing = en_keys - lang_keys
    status = 'OK' if not missing else f'MISSING {len(missing)}'
    print(f'{lang}: {len(lang_keys)} keys - {status}')
    if missing:
        for m in sorted(missing)[:5]:
            print(f'  -> {m}')
