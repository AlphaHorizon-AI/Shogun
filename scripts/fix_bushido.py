import pathlib

# Fix remaining Bushido strings
f = pathlib.Path(r'c:\Users\mdper\Documents\Projekter\Shogun\frontend\src\pages\Bushido.tsx')
content = f.read_text(encoding='utf-8')

rep = [
    ("No recommendations yet. Run a Bushido job to generate insights.",
     "{t('bushido.no_recommendations')}"),
    ("The Bushido engine uses formal verification loops to ensure that all behavioral optimizations remain strictly within the bounds defined in the Kaizen constitution.",
     "{t('bushido.formal_verification_desc')}"),
]

for old, new in rep:
    if old in content:
        content = content.replace(old, new, 1)
        print(f"Fixed: {old[:50]}...")
    else:
        print(f"NOT FOUND: {old[:50]}...")

f.write_text(content, encoding='utf-8')
print("Done")
