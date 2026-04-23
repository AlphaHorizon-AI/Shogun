import json, pathlib
f = pathlib.Path(r'c:\Users\mdper\Documents\Projekter\Shogun\frontend\src\i18n\en.json')
d = json.loads(f.read_text(encoding='utf-8'))
print(f"Keys: {len(d)}")
print(f"Katana keys: {len(d.get('katana', {}))}")
