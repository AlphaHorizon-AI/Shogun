import json, pathlib

d = pathlib.Path(r'c:\Users\mdper\Documents\Projekter\Shogun\frontend\src\i18n')
for f in sorted(d.glob('*.json')):
    data = json.loads(f.read_text(encoding='utf-8'))
    body = data.get('guide', {}).get('disclaimer_body', '')
    has_os = 'open-source' in body.lower() or 'open source' in body.lower()
    status = "CONTAINS OPEN-SOURCE" if has_os else "clean"
    print(f"{f.stem}: {status}")
    print(f"  -> {body[:100]}...")
