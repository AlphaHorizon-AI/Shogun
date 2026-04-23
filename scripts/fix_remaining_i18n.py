import pathlib

SRC = pathlib.Path(r'c:\Users\mdper\Documents\Projekter\Shogun\frontend\src\pages')

def fix_file(filename, replacements):
    f = SRC / filename
    content = f.read_text(encoding='utf-8')
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new, 1)
            print(f"  Fixed: {old[:60]}...")
        else:
            print(f"  SKIP: {old[:60]}...")
    f.write_text(content, encoding='utf-8')
    print(f"OK {filename}")

# Fix Chat.tsx remaining
print("\n=== Chat.tsx ===")
fix_file('Chat.tsx', [
    ("Comms History", "{t('chat.comms_history')}"),
    ("Restore\n", "{t('chat.restore')}\n"),
    ("Clear All History", "{t('chat.clear_all_history')}"),
    # Fix the error message which uses string concatenation
    ('Terminal bridge interrupted. Check backend connectivity.',
     "${t('chat.bridge_interrupted')}"),
])

# Fix Updates.tsx remaining
print("\n=== Updates.tsx ===")
fix_file('Updates.tsx', [
    (">Released: {", ">{t('updates_page.released')}: {"),
    (">Last checked: {", ">{t('updates_page.last_checked')}: {"),
    ("Last checked:", "{t('updates_page.last_checked')}:"),
])

print("\nDone!")
