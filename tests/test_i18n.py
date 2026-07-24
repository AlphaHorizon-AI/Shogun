from shogun.api.i18n import LANGUAGES


def test_hindi_language_pack_is_available() -> None:
    hindi = next(language for language in LANGUAGES if language["code"] == "hi")

    assert hindi == {
        "code": "hi",
        "name": "हिन्दी",
        "englishName": "Hindi",
        "flag": "🇮🇳",
    }
