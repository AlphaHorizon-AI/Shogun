"""Add routing profile name translations to all i18n files."""
import json
from pathlib import Path
I18N = Path(__file__).resolve().parent.parent / "frontend" / "src" / "i18n"

KEYS = {
  "en": {"routing_balanced":"Balanced (Default)","routing_quality":"Quality First","routing_cost":"Cost Optimized"},
  "da": {"routing_balanced":"Balanceret (Standard)","routing_quality":"Kvalitet F\u00f8rst","routing_cost":"Omkostningsoptimeret"},
  "de": {"routing_balanced":"Ausgewogen (Standard)","routing_quality":"Qualit\u00e4t Zuerst","routing_cost":"Kostenoptimiert"},
  "es": {"routing_balanced":"Equilibrado (Predeterminado)","routing_quality":"Calidad Primero","routing_cost":"Costo Optimizado"},
  "fr": {"routing_balanced":"\u00c9quilibr\u00e9 (Par d\u00e9faut)","routing_quality":"Qualit\u00e9 d'Abord","routing_cost":"Co\u00fbt Optimis\u00e9"},
  "it": {"routing_balanced":"Bilanciato (Predefinito)","routing_quality":"Qualit\u00e0 Prima","routing_cost":"Costo Ottimizzato"},
  "ja": {"routing_balanced":"\u30d0\u30e9\u30f3\u30b9 (\u30c7\u30d5\u30a9\u30eb\u30c8)","routing_quality":"\u54c1\u8cea\u512a\u5148","routing_cost":"\u30b3\u30b9\u30c8\u6700\u9069\u5316"},
  "ko": {"routing_balanced":"\uade0\ud615 (\uae30\ubcf8)","routing_quality":"\ud488\uc9c8 \uc6b0\uc120","routing_cost":"\ube44\uc6a9 \ucd5c\uc801\ud654"},
  "no": {"routing_balanced":"Balansert (Standard)","routing_quality":"Kvalitet F\u00f8rst","routing_cost":"Kostnadsoptimalisert"},
  "pl": {"routing_balanced":"Zr\u00f3wnowa\u017cony (Domy\u015blny)","routing_quality":"Jako\u015b\u0107 Najpierw","routing_cost":"Optymalizacja Koszt\u00f3w"},
  "pt": {"routing_balanced":"Equilibrado (Padr\u00e3o)","routing_quality":"Qualidade Primeiro","routing_cost":"Custo Otimizado"},
  "sv": {"routing_balanced":"Balanserad (Standard)","routing_quality":"Kvalitet F\u00f6rst","routing_cost":"Kostnadsoptimerad"},
  "uk": {"routing_balanced":"\u0417\u0431\u0430\u043b\u0430\u043d\u0441\u043e\u0432\u0430\u043d\u0438\u0439 (\u0417\u0430 \u0437\u0430\u043c\u043e\u0432\u0447.)","routing_quality":"\u042f\u043a\u0456\u0441\u0442\u044c \u041f\u0435\u0440\u0448","routing_cost":"\u041e\u043f\u0442\u0438\u043c\u0456\u0437\u0430\u0446\u0456\u044f \u0412\u0430\u0440\u0442\u043e\u0441\u0442\u0456"},
  "zh": {"routing_balanced":"\u5e73\u8861 (\u9ed8\u8ba4)","routing_quality":"\u8d28\u91cf\u4f18\u5148","routing_cost":"\u6210\u672c\u4f18\u5316"},
}

for lang, keys in KEYS.items():
    fp = I18N / f"{lang}.json"
    if not fp.exists(): continue
    data = json.loads(fp.read_text(encoding="utf-8"))
    data.setdefault("profile", {}).update(keys)
    fp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK {lang}")
print("Done.")
