import pathlib, re

f = pathlib.Path(r'c:\Users\mdper\Documents\Projekter\Shogun\frontend\src\i18n\en.json')
content = f.read_text(encoding='utf-8')

# Fix the corrupted disclaimer_body line
# Find the line with disclaimer_body and fix it
lines = content.split('\n')
for i, line in enumerate(lines):
    if '"disclaimer_body"' in line:
        # Extract up to the first proper closing: own risk.",
        # The line has duplicated text after the first "own risk.","
        match = re.search(r'("disclaimer_body":\s*".*?own risk\.")', line)
        if match:
            fixed = '    ' + match.group(1) + ','
            if line.strip() != fixed.strip():
                lines[i] = fixed
                print(f"Fixed line {i+1}")
                print(f"  WAS: {line[:120]}...")
                print(f"  NOW: {fixed[:120]}...")
            else:
                print(f"Line {i+1} already clean")
        break

content = '\n'.join(lines)

# Verify JSON is valid
import json
try:
    data = json.loads(content)
    print("JSON is valid!")
    print(f"disclaimer_body: {data['guide']['disclaimer_body'][:80]}...")
except json.JSONDecodeError as e:
    print(f"JSON STILL INVALID: {e}")

f.write_text(content, encoding='utf-8')
print("File saved.")
