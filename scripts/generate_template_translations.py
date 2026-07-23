"""Generate offline translations for the built-in AgentFlow template catalogs.

Only built-in catalog copy may be sent to a configured LibreTranslate-compatible
service. The local Argos provider keeps all text on-device. Custom templates,
user content, configuration, and runtime data are never read or transmitted.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

from shogun.api.agent_flow import _flow_stack_templates

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "shogun" / "resources" / "flow_templates.json"
OUTPUT = ROOT / "frontend" / "src" / "i18n" / "templates"

LANGUAGES = ("da", "de", "es", "fr", "it", "ja", "ko", "no", "pl", "pt", "sv", "uk", "zh")
ARGOS_LANGUAGE_CODES = {"no": "nb"}
MANUAL_OVERRIDES = {
    "no": {
        "Orchestrator": "Orkestrator",
        "FAQ Generator": "FAQ-generator",
        "NDA Generator": "NDA-generator",
        "Quiz Generator": "Quizgenerator",
        "Business Case Builder": "Forretningscase-bygger",
    },
    "pl": {
        "Orchestrator": "Orkiestrator",
        "Proofread & Edit": "Korekta i redakcja",
        "PR Media List Builder": "Kreator listy mediów PR",
        "Enterprise Research-to-Whitepaper Program": (
            "Korporacyjny program badawczy do tworzenia raportów eksperckich"
        ),
    },
    "sv": {
        "Blank Flow": "Tomt flöde",
        "Flow Stacking": "Flödesstapling",
        "Orchestrator": "Orkestrator",
        "Legal & Compliance": "Juridik och regelefterlevnad",
        "Incident & Resilience": "Incidenter och motståndskraft",
        "Coding Agent Stacks": "Stackar för kodningsagenter",
        "Intermediate": "Medelsvår",
        "Proofread & Edit": "Korrekturläs och redigera",
        "Landing Page Copy": "Text för landningssida",
        "FAQ Generator": "FAQ-generator",
        "SOW/Proposal Generator": "SOW-/offertgenerator",
        "Incident Report Generator": "Generator för incidentrapporter",
        "Ad Copy Generator": "Generator för annonstext",
        "PR Media List Builder": "Byggare för PR-medielistor",
        "Resume Screener": "CV-granskare",
        "NDA Generator": "NDA-generator",
        "Quiz Generator": "Quizgenerator",
        "Intelligent Lead Nurture Sequence": "Intelligent sekvens för leadbearbetning",
        "M&A Due Diligence Research": "Due diligence-analys för fusioner och förvärv",
        "Operations Dashboard Builder": "Byggare för verksamhetsöversikter",
        "Business Case Builder": "Byggare för affärscase",
        "Enterprise Technology Horizon Scan": ("Företagsövergripande teknisk omvärldsanalys"),
        "Enterprise Market Entry Program": ("Företagsövergripande program för marknadsinträde"),
        "Transformation Market Entry Program": ("Transformationsprogram för marknadsinträde"),
        "Enterprise Innovation Pipeline": "Företagsövergripande innovationspipeline",
        "Transformation Innovation Pipeline": "Transformationspipeline för innovation",
        "Enterprise Brand Health Command": ("Företagsövergripande styrning av varumärkeshälsa"),
        "Transformation Brand Health Command": ("Transformationsstyrning av varumärkeshälsa"),
        "Enterprise Retention Recovery Program": ("Företagsövergripande program för att återvinna kundlojalitet"),
        "Regional Retention Recovery Program": ("Regionalt program för att återvinna kundlojalitet"),
        "Enterprise Enterprise Risk Assurance": "Företagsövergripande risksäkring",
        "Enterprise Learning Academy Operation": ("Företagsövergripande drift av lärandeakademi"),
        "Enterprise Multilingual Knowledge Hub": ("Företagsövergripande flerspråkig kunskapshubb"),
        "Refactor Stack": "Refaktoriseringsstack",
        "Test Generation Stack": "Stack för testgenerering",
    },
}

UI_COPY = {
    "create_agent_flow": "Create Agent Flow",
    "choose_template": "Choose a template or start from scratch",
    "templates": "Templates",
    "blank_flow": "Blank Flow",
    "all_templates": "All Templates",
    "search_templates": "Search templates...",
    "templates_unavailable": "Templates unavailable",
    "no_templates": "No templates match your search",
    "nodes": "nodes",
    "flow_stacking": "Flow Stacking",
    "flow_stacking_subtitle": "Compose AgentFlows into connected, orchestrated systems.",
    "built_in_stacks": "built-in stacks",
    "stack_builder": "Stack Builder",
    "stack_templates": "Stack Templates",
    "orchestrator": "Orchestrator",
    "search_stack_templates": "Search Flow Stack templates",
    "all_stack_categories": "All Flow Stack Categories",
    "reusable_templates": "reusable templates",
    "shown": "shown",
    "phases": "phases",
    "resumable": "Resumable",
    "open_program": "Open long-running program",
    "building_stack": "Building your Flow Stack...",
    "could_not_create_stack": "Could not create this stack.",
}

DIFFICULTY = {
    "beginner": "Beginner",
    "intermediate": "Intermediate",
    "advanced": "Advanced",
    "custom": "Custom",
    "long-running": "Long-running",
}


def _translate_all_libre(
    texts: list[str],
    language: str,
    endpoint: str,
    api_key: str | None,
) -> dict[str, str]:
    unique = list(dict.fromkeys(text for text in texts if text))
    translated: dict[str, str] = {}
    batch_size = 32
    for start in range(0, len(unique), batch_size):
        batch = unique[start : start + batch_size]
        payload = {
            "q": batch,
            "source": "en",
            "target": ARGOS_LANGUAGE_CODES.get(language, language),
            "format": "text",
        }
        if api_key:
            payload["api_key"] = api_key
        request = urllib.request.Request(
            endpoint.rstrip("/") + "/translate",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Shogun-Template-Localization/1.0",
            },
        )
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.loads(response.read().decode("utf-8"))
        values = result.get("translatedText")
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list) or len(values) != len(batch):
            raise RuntimeError(
                f"LibreTranslate batch failed: expected {len(batch)}, got "
                f"{len(values) if isinstance(values, list) else type(values).__name__}"
            )
        translated.update(zip(batch, (str(value).strip() for value in values), strict=True))
        print(f"{language}: {min(start + batch_size, len(unique))}/{len(unique)}", flush=True)
    return translated


def _install_argos_models(languages: list[str]) -> None:
    from argostranslate import package, translate

    installed_pairs = {
        (translation.from_lang.code, translation.to_lang.code)
        for language in translate.get_installed_languages()
        for translation in language.translations_from
    }
    targets = {ARGOS_LANGUAGE_CODES.get(language, language) for language in languages}
    missing = {target for target in targets if ("en", target) not in installed_pairs}
    if not missing:
        return
    package.update_package_index()
    available = package.get_available_packages()
    for target in sorted(missing):
        match = next(
            (item for item in available if item.from_code == "en" and item.to_code == target),
            None,
        )
        if match is None:
            raise RuntimeError(f"No Argos English-to-{target} package is available")
        print(f"{target}: downloading Argos model", flush=True)
        package.install_from_path(match.download())


def _translate_all_argos(texts: list[str], language: str) -> dict[str, str]:
    from argostranslate import translate

    target = ARGOS_LANGUAGE_CODES.get(language, language)
    translator = translate.get_translation_from_codes("en", target)
    if translator is None:
        raise RuntimeError(f"Argos English-to-{target} model is not installed")
    unique = list(dict.fromkeys(text for text in texts if text))
    translated: dict[str, str] = {}
    for index, text in enumerate(unique, start=1):
        value = translator.translate(text).strip()
        if value.casefold() == text.casefold() and " " in text:
            sentence_source = text.capitalize()
            added_period = sentence_source[-1] not in ".!?"
            if added_period:
                sentence_source += "."
            retry = translator.translate(sentence_source).strip()
            if retry.casefold() != sentence_source.casefold():
                if added_period and retry.endswith("."):
                    retry = retry[:-1].rstrip()
                value = retry[:1].upper() + retry[1:]
        translated[text] = value
        if index % 25 == 0 or index == len(unique):
            print(f"{language}: {index}/{len(unique)}", flush=True)
    return translated


def _source_payload() -> tuple[list[dict], list[dict], list[str]]:
    agent_templates = json.loads(SOURCE.read_text(encoding="utf-8"))["templates"]
    stack_templates = _flow_stack_templates()
    copy = [*UI_COPY.values(), *DIFFICULTY.values()]
    for item in agent_templates:
        copy.extend((item["name"], item["description"], item["category"]))
    for item in stack_templates:
        copy.extend((item["name"], item["description"], item["category"], item["duration_label"]))
        copy.extend(node["label"] for node in item.get("builder_nodes", []))
    return agent_templates, stack_templates, copy


def _build_locale(
    language: str,
    agent_templates: list[dict],
    stack_templates: list[dict],
    translations: dict[str, str],
) -> dict:
    overrides = MANUAL_OVERRIDES.get(language, {})

    def tr(value: str) -> str:
        return overrides.get(value, translations.get(value, value))

    return {
        "ui": {key: tr(value) for key, value in UI_COPY.items()},
        "categories": {item["category"]: tr(item["category"]) for item in [*agent_templates, *stack_templates]},
        "difficulty": {key: tr(value) for key, value in DIFFICULTY.items()},
        "agentFlow": {
            item["id"]: {"name": tr(item["name"]), "description": tr(item["description"])} for item in agent_templates
        },
        "flowStack": {
            item["id"]: {
                "name": tr(item["name"]),
                "description": tr(item["description"]),
                "duration_label": tr(item["duration_label"]),
                "builder_labels": {node["id"]: tr(node["label"]) for node in item.get("builder_nodes", [])},
            }
            for item in stack_templates
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--languages", nargs="*", default=list(LANGUAGES))
    parser.add_argument(
        "--provider",
        choices=("libretranslate", "argos"),
        default="libretranslate",
    )
    parser.add_argument(
        "--endpoint",
        default="https://translate.cutie.dating",
        help="LibreTranslate-compatible base URL",
    )
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    invalid = sorted(set(args.languages) - set(LANGUAGES))
    if invalid:
        raise SystemExit(f"Unsupported languages: {', '.join(invalid)}")
    if args.provider == "argos":
        _install_argos_models(args.languages)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    agent_templates, stack_templates, copy = _source_payload()
    english = {text: text for text in copy}
    (OUTPUT / "en.json").write_text(
        json.dumps(_build_locale("en", agent_templates, stack_templates, english), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for language in args.languages:
        target = OUTPUT / f"{language}.json"
        if target.exists() and not args.force:
            existing = json.loads(target.read_text(encoding="utf-8"))
            if len(existing.get("agentFlow", {})) == len(agent_templates) and len(existing.get("flowStack", {})) == len(
                stack_templates
            ):
                print(f"{language}: complete; skipping", flush=True)
                continue
        translations = (
            _translate_all_argos(copy, language)
            if args.provider == "argos"
            else _translate_all_libre(copy, language, args.endpoint, args.api_key)
        )
        payload = _build_locale(language, agent_templates, stack_templates, translations)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
