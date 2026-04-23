import json
import os

# Updated disclaimer_body for all languages — "free to use" replaces "free and open-source"
updated_body = {
    "en": "Shogun is a free to use AI agent orchestration framework. It is intended to help users build, manage, and operate autonomous AI workflows, but it does not guarantee accuracy, completeness, reliability, or suitability for any particular purpose. Shogun is provided as is, and use of the framework is entirely at the user's own risk.",
    "da": "Shogun er et gratis AI-agentorkestreringsrammeværk. Det er beregnet til at hjælpe brugere med at opbygge, administrere og drive autonome AI-arbejdsgange, men det garanterer ikke nøjagtighed, fuldstændighed, pålidelighed eller egnethed til noget bestemt formål. Shogun leveres som det er, og brug af rammeværket er helt på brugerens eget ansvar.",
    "de": "Shogun ist ein kostenloses Framework zur Orchestrierung von KI-Agenten. Es soll Benutzern helfen, autonome KI-Workflows zu erstellen, zu verwalten und zu betreiben, garantiert jedoch keine Genauigkeit, Vollständigkeit, Zuverlässigkeit oder Eignung für einen bestimmten Zweck. Shogun wird im Ist-Zustand bereitgestellt, und die Nutzung erfolgt ausschließlich auf eigenes Risiko.",
    "es": "Shogun es un framework gratuito de orquestación de agentes de IA. Está diseñado para ayudar a los usuarios a construir, gestionar y operar flujos de trabajo de IA autónomos, pero no garantiza exactitud, completitud, fiabilidad o idoneidad para ningún propósito particular. Shogun se proporciona tal cual, y su uso es enteramente bajo el riesgo del usuario.",
    "fr": "Shogun est un framework gratuit d'orchestration d'agents IA. Il est conçu pour aider les utilisateurs à construire, gérer et opérer des workflows IA autonomes, mais ne garantit pas l'exactitude, la complétude, la fiabilité ou l'adéquation à un usage particulier. Shogun est fourni tel quel, et l'utilisation du framework est entièrement aux risques de l'utilisateur.",
    "it": "Shogun è un framework gratuito di orchestrazione di agenti IA. Ha lo scopo di aiutare gli utenti a costruire, gestire e operare flussi di lavoro IA autonomi, ma non garantisce accuratezza, completezza, affidabilità o idoneità per alcuno scopo particolare. Shogun è fornito così com'è, e l'utilizzo del framework è interamente a rischio dell'utente.",
    "ja": "Shogunは無料のAIエージェントオーケストレーションフレームワークです。ユーザーが自律型AIワークフローを構築、管理、運用することを支援するために設計されていますが、正確性、完全性、信頼性、または特定の目的への適合性を保証するものではありません。Shogunは現状のまま提供され、フレームワークの使用は完全にユーザー自身のリスクで行われます。",
    "ko": "Shogun은 무료 AI 에이전트 오케스트레이션 프레임워크입니다. 사용자가 자율 AI 워크플로를 구축, 관리 및 운영하도록 돕기 위해 설계되었지만, 정확성, 완전성, 신뢰성 또는 특정 목적에 대한 적합성을 보장하지 않습니다. Shogun은 있는 그대로 제공되며, 프레임워크 사용은 전적으로 사용자의 책임입니다.",
    "no": "Shogun er et gratis rammeverk for orkestrering av AI-agenter. Det er designet for å hjelpe brukere med å bygge, administrere og drifte autonome AI-arbeidsflyter, men garanterer ikke nøyaktighet, fullstendighet, pålitelighet eller egnethet for noe bestemt formål. Shogun leveres som det er, og bruk er helt på brukerens egen risiko.",
    "pl": "Shogun to darmowy framework do orkiestracji agentów AI. Został zaprojektowany, aby pomóc użytkownikom w budowaniu, zarządzaniu i obsłudze autonomicznych procesów AI, ale nie gwarantuje dokładności, kompletności, niezawodności ani przydatności do określonego celu. Shogun jest dostarczany w stanie takim, jaki jest, a korzystanie z niego odbywa się wyłącznie na ryzyko użytkownika.",
    "pt": "Shogun é um framework gratuito de orquestração de agentes de IA. É projetado para ajudar os utilizadores a construir, gerir e operar fluxos de trabalho de IA autónomos, mas não garante precisão, completude, fiabilidade ou adequação a qualquer finalidade específica. Shogun é fornecido no estado em que se encontra, e a utilização do framework é inteiramente por conta e risco do utilizador.",
    "sv": "Shogun är ett kostnadsfritt ramverk för orkestrering av AI-agenter. Det är utformat för att hjälpa användare att bygga, hantera och driva autonoma AI-arbetsflöden, men garanterar inte noggrannhet, fullständighet, tillförlitlighet eller lämplighet för något visst ändamål. Shogun tillhandahålls i befintligt skick, och användning av ramverket sker helt på användarens egen risk.",
    "uk": "Shogun — це безкоштовний фреймворк для оркестрації AI-агентів. Він призначений допомогти користувачам будувати, керувати та експлуатувати автономні AI-робочі процеси, але не гарантує точність, повноту, надійність чи придатність для будь-якої конкретної мети. Shogun надається як є, і використання фреймворку повністю на ризик користувача.",
    "zh": "Shogun是一个免费的AI代理编排框架。它旨在帮助用户构建、管理和运营自主AI工作流，但不保证准确性、完整性、可靠性或对任何特定目的的适用性。Shogun按原样提供，使用该框架完全由用户自行承担风险。"
}

i18n_dir = r"c:\Users\mdper\Documents\Projekter\Shogun\frontend\src\i18n"

for lang, body in updated_body.items():
    file_path = os.path.join(i18n_dir, f"{lang}.json")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "guide" in data and "disclaimer_body" in data["guide"]:
            old = data["guide"]["disclaimer_body"]
            data["guide"]["disclaimer_body"] = body
            print(f"[{lang}] Updated disclaimer_body")
        else:
            print(f"[{lang}] WARNING: guide.disclaimer_body not found!")

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
    else:
        print(f"[{lang}] File not found: {file_path}")

print("\nDone — all disclaimer_body values updated to 'free to use' phrasing.")
