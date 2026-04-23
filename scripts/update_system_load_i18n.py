"""Replace cpu_affinity with cpu_usage, memory_usage, disk_usage in all i18n files."""
import json
from pathlib import Path

I18N_DIR = Path(__file__).resolve().parent.parent / "frontend" / "src" / "i18n"

TRANSLATIONS = {
    "da": {"cpu_usage": "CPU", "memory_usage": "Hukommelse", "disk_usage": "Disk"},
    "de": {"cpu_usage": "CPU", "memory_usage": "Arbeitsspeicher", "disk_usage": "Festplatte"},
    "es": {"cpu_usage": "CPU", "memory_usage": "Memoria", "disk_usage": "Disco"},
    "fr": {"cpu_usage": "CPU", "memory_usage": "Mémoire", "disk_usage": "Disque"},
    "it": {"cpu_usage": "CPU", "memory_usage": "Memoria", "disk_usage": "Disco"},
    "ja": {"cpu_usage": "CPU", "memory_usage": "メモリ", "disk_usage": "ディスク"},
    "ko": {"cpu_usage": "CPU", "memory_usage": "메모리", "disk_usage": "디스크"},
    "no": {"cpu_usage": "CPU", "memory_usage": "Minne", "disk_usage": "Disk"},
    "pl": {"cpu_usage": "CPU", "memory_usage": "Pamięć", "disk_usage": "Dysk"},
    "pt": {"cpu_usage": "CPU", "memory_usage": "Memória", "disk_usage": "Disco"},
    "sv": {"cpu_usage": "CPU", "memory_usage": "Minne", "disk_usage": "Disk"},
    "uk": {"cpu_usage": "CPU", "memory_usage": "Пам'ять", "disk_usage": "Диск"},
    "zh": {"cpu_usage": "CPU", "memory_usage": "内存", "disk_usage": "磁盘"},
}

for lang, keys in TRANSLATIONS.items():
    fp = I18N_DIR / f"{lang}.json"
    if not fp.exists():
        print(f"SKIP {lang} (not found)")
        continue

    data = json.loads(fp.read_text(encoding="utf-8"))
    dashboard = data.get("dashboard", {})

    # Remove old key
    dashboard.pop("cpu_affinity", None)

    # Add new keys
    for k, v in keys.items():
        dashboard[k] = v

    data["dashboard"] = dashboard
    fp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK {lang}: updated")

print("\nDone.")
