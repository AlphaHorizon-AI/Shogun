"""Build static, offline Guide translation catalogs.

The Guide intentionally contains rich JSX instead of one enormous translated
HTML blob. This utility extracts its user-facing English text fragments and
uses Google Translate's public web endpoint in HTML batches. The generated
catalogs are committed and loaded locally at runtime; Shogun never sends Guide
content or operator data to a translation service while the app is running.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend" / "src" / "pages" / "Guide.tsx"
OUTPUT = ROOT / "frontend" / "src" / "i18n" / "guide"
LANGUAGES = ("da", "de", "es", "fr", "it", "ja", "ko", "no", "pl", "pt", "sv", "uk", "zh")

UTILITY_MARKERS = (
    "bg-", "text-", "border-", "hover:", "md:", "lg:", "xl:", "flex", "grid",
    "space-", "gap-", "rounded", "items-", "justify-", "tracking-", "font-",
    "w-", "h-", "p-", "m-", "animate-", "transition-", "shadow-", "overflow-",
)


def _decode_ts_string(value: str, quote: str) -> str:
    value = value.replace(f"\\{quote}", quote).replace("\\n", "\n").replace("\\t", "\t")
    return value.replace("\\\\", "\\")


def _looks_visible(value: str) -> bool:
    value = " ".join(value.split())
    if len(value) < 2 or not re.search(r"[A-Za-zÀ-ž]", value):
        return False
    if value.startswith(("http://", "https://", "/", "../", "./", "ref-", "data:")):
        return False
    if any(marker in value for marker in (" const ", "useState", "useRef", "=>", "className=", "return (", "import ", "async function")):
        return False
    if value == "Promise":
        return False
    if value in {"onboarding", "reference", "architecture", "safety", "smooth", "start", "root"}:
        return False
    tokens = value.split()
    if sum(any(marker in token for marker in UTILITY_MARKERS) for token in tokens) >= max(1, len(tokens) // 2):
        return False
    if re.fullmatch(r"[a-z][a-z0-9_-]*", value) and "_" in value:
        return False
    return True


def extract_fragments(source: str) -> list[str]:
    fragments: set[str] = set()

    # Literal JSX text nodes, including fragments around <strong>/<code> tags.
    for match in re.finditer(r">([^<>{}]+)<", source, re.S):
        value = " ".join(html.unescape(match.group(1)).split())
        if _looks_visible(value):
            fragments.add(value)

    # Visible strings used by the Guide's data-driven cards and tables.
    fields = r"(?:label|title|desc|description|purpose|term|def|name|subtitle|step|tip|risk|what|action)"
    for quote, pattern in (
        ("'", rf"\b{fields}\s*:\s*'((?:\\.|[^'\\])*)'"),
        ('"', rf'\b{fields}\s*:\s*"((?:\\.|[^"\\])*)"'),
    ):
        for match in re.finditer(pattern, source):
            value = " ".join(_decode_ts_string(match.group(1), quote).split())
            if _looks_visible(value):
                fragments.add(value)

    return sorted(fragments, key=lambda item: (item.lower(), item))


def _translate_batch(items: list[tuple[int, str]], language: str) -> dict[int, str]:
    # Plain-text sentinels keep entries isolated without giving the translation
    # model HTML tags that it can merge into neighboring prose.
    payload = "".join(f"\n[[[SHOGUN_{index}]]]\n{text}" for index, text in items)
    query = urllib.parse.urlencode({
        "client": "gtx", "sl": "en", "tl": language, "dt": "t", "q": payload,
    })
    request = urllib.request.Request(
        f"https://translate.googleapis.com/translate_a/single?{query}",
        headers={"User-Agent": "Shogun-Guide-Catalog/1.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        result = json.loads(response.read().decode("utf-8"))
    translated_text = "".join(part[0] for part in result[0] if part and part[0])
    markers = list(re.finditer(r"\[\[\[\s*SHOGUN_(\d+)\s*\]\]\]", translated_text, re.I))
    parsed: dict[int, str] = {}
    for position, marker in enumerate(markers):
        start = marker.end()
        end = markers[position + 1].start() if position + 1 < len(markers) else len(translated_text)
        parsed[int(marker.group(1))] = translated_text[start:end].strip()
    return parsed


def translate_catalog(fragments: list[str], language: str) -> dict[str, str]:
    translated: dict[int, str] = {}

    def request_batch(items: list[tuple[int, str]]) -> dict[int, str]:
        for attempt in range(4):
            try:
                return _translate_batch(items, language)
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(1.5 * (attempt + 1))
        return {}

    batch: list[tuple[int, str]] = []
    batch_chars = 0
    batches: list[list[tuple[int, str]]] = []
    for index, fragment in enumerate(fragments):
        cost = len(fragment) + 32
        if batch and batch_chars + cost > 3500:
            batches.append(batch)
            batch, batch_chars = [], 0
        batch.append((index, fragment))
        batch_chars += cost
    if batch:
        batches.append(batch)

    for number, current in enumerate(batches, start=1):
        translated.update(request_batch(current))
        print(f"{language}: batch {number}/{len(batches)}", flush=True)

    # Google occasionally drops span IDs from a large HTML response. Repair
    # only those missing entries in small batches, then individually, so a
    # transient parser omission never leaves visible Guide prose in English.
    missing = [(index, fragment) for index, fragment in enumerate(fragments) if not translated.get(index)]
    for offset in range(0, len(missing), 10):
        try:
            translated.update(request_batch(missing[offset:offset + 10]))
        except Exception:
            # The individual fallback below isolates a malformed fragment.
            pass
    missing = [(index, fragment) for index, fragment in enumerate(fragments) if not translated.get(index)]
    for item in missing:
        try:
            translated.update(request_batch([item]))
        except Exception as error:
            print(f"{language}: could not translate fragment {item[0]} ({error})", flush=True)
    if missing:
        print(f"{language}: repaired {len(missing)} dropped fragments", flush=True)

    return {
        source: translated.get(index) or source
        for index, source in enumerate(fragments)
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extract-only", action="store_true")
    parser.add_argument(
        "--repair-existing",
        action="store_true",
        help="Retry catalog entries that still equal their English source text.",
    )
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Translate only newly extracted fragments and preserve existing translations.",
    )
    parser.add_argument("--languages", nargs="*", default=list(LANGUAGES))
    args = parser.parse_args()

    fragments = extract_fragments(SOURCE.read_text(encoding="utf-8"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "en.json").write_text(
        json.dumps({fragment: fragment for fragment in fragments}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Extracted {len(fragments)} Guide text fragments.")
    if args.extract_only:
        return

    for language in args.languages:
        if language not in LANGUAGES:
            raise SystemExit(f"Unsupported language: {language}")
        catalog_path = OUTPUT / f"{language}.json"
        if args.missing_only and catalog_path.exists():
            existing = json.loads(catalog_path.read_text(encoding="utf-8"))
            pending = [fragment for fragment in fragments if fragment not in existing]
            print(f"{language}: translating {len(pending)} new fragments", flush=True)
            existing.update(translate_catalog(pending, language))
            catalog = {fragment: existing.get(fragment, fragment) for fragment in fragments}
        elif args.repair_existing and catalog_path.exists():
            existing = json.loads(catalog_path.read_text(encoding="utf-8"))
            pending = [fragment for fragment in fragments if existing.get(fragment, fragment) == fragment]
            print(f"{language}: retrying {len(pending)} unchanged fragments", flush=True)
            existing.update(translate_catalog(pending, language))
            catalog = {fragment: existing.get(fragment, fragment) for fragment in fragments}
        else:
            catalog = translate_catalog(fragments, language)
        catalog_path.write_text(
            json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
