import glob

for f in glob.glob('frontend/src/i18n/*.json'):
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    content = content.replace('"Cloud Providers"', '"AI Model Provider"')
    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)
print("Updated json files.")
