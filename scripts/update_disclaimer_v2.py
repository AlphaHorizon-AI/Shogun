import json
import os

# Full dictionary of the new translations
translations = {
    "en": {
        "disclaimer_title": "Disclaimer",
        "disclaimer_body": "Shogun is a free and open-source AI agent orchestration framework. It is intended to help users build, manage, and operate autonomous AI workflows, but it does not guarantee accuracy, completeness, reliability, or suitability for any particular purpose. Shogun is provided as is, and use of the framework is entirely at the user’s own risk.",
        "disclaimer_oversight": "Users are responsible for ensuring appropriate human oversight and for validating all outputs, actions, and decisions produced with or through Shogun. Human review should remain in the loop at all times, particularly in legal, financial, regulatory, security, or other high-impact use cases."
    },
    "da": {
        "disclaimer_title": "Ansvarsfraskrivelse",
        "disclaimer_body": "Shogun er et gratis og open source-rammeværk til orkestrering af AI-agenter. Det er beregnet til at hjælpe brugere med at opbygge, administrere og drive autonome AI-arbejdsgange, men det garanterer ikke nøjagtighed, fuldstændighed, pålidelighed eller egnethed til noget bestemt formål. Shogun leveres som beset, og brug af rammeværket er helt på brugerens eget ansvar.",
        "disclaimer_oversight": "Brugere er ansvarlige for at sikre passende menneskeligt tilsyn og for at validere alle outputs, handlinger og beslutninger produceret med eller gennem Shogun. Menneskelig gennemgang bør forblive i loopet til enhver tid, især i juridiske, finansielle, regulatoriske, sikkerhedsmæssige eller andre brugstilfælde med stor indvirkning."
    },
    "de": {
        "disclaimer_title": "Haftungsausschluss",
        "disclaimer_body": "Shogun ist ein kostenloses Open-Source-Framework zur Orchestrierung von KI-Agenten. Es soll Benutzern dabei helfen, autonome KI-Workflows zu erstellen, zu verwalten und zu betreiben, garantiert jedoch keine Genauigkeit, Vollständigkeit, Zuverlässigkeit oder Eignung für einen bestimmten Zweck. Shogun wird im Ist-Zustand bereitgestellt, und die Nutzung des Frameworks erfolgt ausschließlich auf eigenes Risiko des Benutzers.",
        "disclaimer_oversight": "Die Benutzer sind dafür verantwortlich, eine angemessene menschliche Aufsicht sicherzustellen und alle mit oder durch Shogun erzeugten Ergebnisse, Aktionen und Entscheidungen zu validieren. Eine menschliche Überprüfung sollte jederzeit gewährleistet sein, insbesondere in rechtlichen, finanziellen, regulatorischen, sicherheitsrelevanten oder anderen contexts mit hoher Auswirkung."
    },
    "es": {
        "disclaimer_title": "Descargo de responsabilidad",
        "disclaimer_body": "Shogun es un marco de orquestación de agentes de IA gratuito y de código abierto. Está destinado a ayudar a los usuarios a construir, gestionar y operar flujos de trabajo de IA autónomos, pero no garantiza la precisión, integridad, fiabilidad o idoneidad para cualquier propósito particular. Shogun se proporciona tal cual, y el uso del marco es bajo el propio riesgo del usuario.",
        "disclaimer_oversight": "Los usuarios son responsables de garantizar una supervisión humana adecuada y de validar todos los resultados, acciones y decisiones producidos con o a través de Shogun. La revisión humana debe permanecer en el proceso en todo momento, particularmente en casos de uso legales, financieros, regulatorios, de seguridad u otros de alto impacto."
    },
    "fr": {
        "disclaimer_title": "Clause de non-responsabilité",
        "disclaimer_body": "Shogun est un framework d'orchestration d'agents d'IA gratuit et open-source. Il est destiné à aider les utilisateurs à construire, gérer et exploiter des flux de travail d'IA autonomes, mais il ne garantit pas l'exactitude, l'exhaustivité, la fiabilité ou l'adéquation à un usage particulier. Shogun est fourni en l'état, et l'utilisation du framework est aux risques et périls de l'utilisateur.",
        "disclaimer_oversight": "Les utilisateurs sont responsables de s'assurer d'une supervision humaine appropriée et de valider tous les résultats, actions et décisions produits avec ou via Shogun. Une révision humaine doit rester présente à tout moment, en particulier dans les cas d'utilisation juridiques, financiers, réglementaires, de sécurité ou autres contextes à fort impact."
    },
    "it": {
        "disclaimer_title": "Esclusione di responsabilità",
        "disclaimer_body": "Shogun è un framework di orchestrazione di agenti IA gratuito e open-source. È pensato per aiutare gli utenti a costruire, gestire e operare flussi di lavoro IA autonomi, ma non garantisce accuratezza, completezza, affidabilità o idoneità per alcuno scopo particolare. Shogun è fornito così com'è e l'uso del framework è interamente a rischio dell'utente.",
        "disclaimer_oversight": "Gli utenti sono responsabili di garantire un'adeguata supervisione umana e di convalidare tutti i risultati, le azioni e le decisioni prodotti con o tramite Shogun. La revisione umana dovrebbe rimanere sempre parte del processo, in particolare in casi d'uso legali, finanziari, normativi, di sicurezza o altri ad alto impatto."
    },
    "ja": {
        "disclaimer_title": "免責事項",
        "disclaimer_body": "Shogun は、無料かつオープンソースの AI エージェント オーケストレーション フレームワークです。ユーザーが自律型 AI ワークフローを構築、管理、および運用するのを支援することを目的としていますが、特定の目的における正確性、完全性、信頼性、または適合性を保証するものではありません。Shogun は現状のまま提供され、フレームワークの使用は完全にユーザー自身の責任となります。",
        "disclaimer_oversight": "ユーザーは、適切な人的監視を確保し、Shogun を使用して、または Shogun を通じて生成されたすべての出力、アクション、および決定を検証する責任を負います。特に法的、財務的、規制的、セキュリティ関連、またはその他の影響の大きいユースケースでは、常に人間による確認を介在させる必要があります。"
    },
    "ko": {
        "disclaimer_title": "면책 조항",
        "disclaimer_body": "Shogun은 무료 오픈 소스 AI 에이전트 오케스트레이션 프레임워크입니다. 사용자가 자율 AI 워크플로를 구축, 관리 및 운영할 수 있도록 돕기 위한 것이지만, 특정 목적에 대한 정확성, 완전성, 신뢰성 또는 적합성을 보장하지 않습니다. Shogun은 있는 그대로 제공되며, 프레임워크 사용에 대한 책임은 전적으로 사용자에게 있습니다.",
        "disclaimer_oversight": "사용자는 적절한 인간의 감독을 보장하고 Shogun을 사용하거나 Shogun을 통해 생성된 모든 출력, 작업 및 결정을 검증할 책임이 있습니다. 특히 법률, 재무, 규제, 보안 또는 기타 영향이 큰 사용 사례에서는 인간의 검토가 항상 유지되어야 합니다."
    },
    "no": {
        "disclaimer_title": "Ansvarsfraskrivelse",
        "disclaimer_body": "Shogun er et gratis og åpen kildekode-rammeverk for orkestrering av AI-agenter. Det er ment å hjelpe brukere med å bygge, administrere og operere autonome AI-arbeidsprosesser, men det garanterer ikke nøyaktighet, fullstendighet, pålitelighet eller egnethet for noe bestemt formål. Shogun leveres som den er, og bruk av rammeverket er helt på brukerens egen risiko.",
        "disclaimer_oversight": "Brukere er ansvarlige for å sikre passende menneskelig tilsyn og for å validere alle resultater, handlinger og beslutninger produsert med eller gjennom Shogun. Menneskelig vurdering bør forbli en del av prosessen til enhver tid, spesielt i juridiske, finansielle, regulatoriske, sikkerhetsmessige eller andre brukstilfeller med høy påvirkning."
    },
    "pl": {
        "disclaimer_title": "Zastrzeżenie",
        "disclaimer_body": "Shogun to darmowy i otwarty framework do orkiestracji agentów AI. Ma on na celu pomoc użytkownikom w budowaniu, zarządzaniu i obsłudze autonomicznych przepływów pracy AI, ale nie gwarantuje dokładności, kompletności, niezawodności ani przydatności do jakiegokolwiek konkretnego celu. Shogun jest dostarczany w stanie, w jakim się znajduje, a korzystanie z frameworka odbywa się całkowicie na własne ryzyko użytkownika.",
        "disclaimer_oversight": "Użytkownicy są odpowiedzialni za zapewnienie odpowiedniego nadzoru ludzkiego oraz za sprawdzanie wszystkich wyników, działań i decyzji podejmowanych za pomocą lub za pośrednictwem systemu Shogun. Weryfikacja przez człowieka powinna być zachowana na każdym etapie, szczególnie w przypadkach prawnych, finansowych, regulacyjnych, związanych z bezpieczeństwem lub innych istotnych zastosowaniach."
    },
    "pt": {
        "disclaimer_title": "Isenção de responsabilidade",
        "disclaimer_body": "Shogun é um framework de orquestração de agentes de IA gratuito e de código aberto. Ele se destina a ajudar os usuários a construir, gerenciar e operar fluxos de trabalho de IA autônomos, mas não garante precisão, integridade, confiabilidade ou adequação para qualquer propósito específico. O Shogun é fornecido como está, e o uso do framework é inteiramente por conta e risco do usuário.",
        "disclaimer_oversight": "Os usuários são responsáveis por garantir a supervisão humana adequada e por validar todas as saídas, ações e decisões produzidas com ou por meio do Shogun. A revisão humana deve permanecer presente em todos os momentos, especialmente em casos de uso legais, financeiros, regulatórios, de segurança ou outros de alto impacto."
    },
    "sv": {
        "disclaimer_title": "Ansvarsfriskrivning",
        "disclaimer_body": "Shogun är ett kostnadsfritt ramverk med öppen källkod för orkestrering av AI-agenter. Det är avsett att hjälpa användare att bygga, hantera och driva autonoma AI-arbetsflöden, men det garanterar inte noggrannhet, fullständighet, tillförlitlighet eller lämplighet för något visst ändamål. Shogun tillhandahålls i befintligt skick, och användning av ramverket sker helt på användarens egen risk.",
        "disclaimer_oversight": "Användare ansvarar för att säkerställa lämplig mänsklig tillsyn och för att validera alla utdata, åtgärder och beslut som produceras med eller genom Shogun. Mänsklig granskning bör alltid vara en del av processen, särskilt i juridiska, finansiella, regulatoriska, säkerhetsmässiga eller andra användningsfall med stor inverkan."
    },
    "uk": {
        "disclaimer_title": "Відмова від відповідальності",
        "disclaimer_body": "Shogun — це безкоштовний фреймворк для оркестровки ШІ-агентів з відкритим вихідним кодом. Він призначений для допомоги користувачам у створенні, управлінні та експлуатації автономних робочих процесів ШІ, але він не гарантує точність, повноту, надійність або придатність для будь-якої конкретної мети. Shogun надається «як є», і використання фреймворку здійснюється виключно на власний ризик користувача.",
        "disclaimer_oversight": "Користувачі несуть відповідальність за забезпечення належного нагляду з боку людини та за перевірку всіх результатів, дій і рішень, отриманих за допомогою Shogun. Людський контроль повинен зберігатися на всіх етапах, особливо в юридичних, фінансових, регуляторних, безпекових або інших випадках високого рівня впливу."
    },
    "zh": {
        "disclaimer_title": "免责声明",
        "disclaimer_body": "Shogun 是一个免费且开源的 AI 代理编排框架。它旨在帮助用户构建、管理和运维自主 AI 工作流，但不保证准确性、完整性、可靠性或对任何特定用途的适用性。Shogun 按现状提供，使用该框架的风险完全由用户自行承担。",
        "disclaimer_oversight": "用户负责确保适当的人工监督，并验证使用 Shogun 或通过 Shogun 产生的所有输出、行动和决策。人工审查应在任何时候都保持在流程中，特别是在法律、财务、监管、安全或其他高影响的使用案例中。"
    }
}

i18n_dir = r"c:\Users\mdper\Documents\Projekter\Shogun\frontend\src\i18n"

for lang, content in translations.items():
    file_path = os.path.join(i18n_dir, f"{lang}.json")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if "guide" in data:
            data["guide"].update(content)
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
print("Refactored disclaimer translations applied to all language files.")
