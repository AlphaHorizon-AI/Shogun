import json
import os
import glob

# Full dictionary of translations for the disclaimer and copyright
translations = {
    "da": {
        "common": {"copyright": "© 2026 Alpha Horizon. Alle rettigheder forbeholdes"},
        "guide": {
            "disclaimer_title": "Juridisk ansvarsfraskrivelse",
            "disclaimer_body": "Shogun leveres kun til generel informativ, eksperimentel og operationel brug. Det leveres \"som det er\" og \"som tilgængeligt\", uden nogen form for garantier, udtrykkelige eller underforståede, herunder men ikke begrænset til nøjagtighed, egnethed til et bestemt formål, salgbarhed, tilgængelighed eller ikke-krænkelse. Brugere er eneansvarlige for at evaluere, validere, overvåge og godkende alle outputs, handlinger, konfigurationer eller beslutninger truffet med eller gennem Shogun. Alpha Horizon fraskriver sig ethvert ansvar for direkte, indirekte, tilfældige, følgeskader eller særlige skader som følge af brugen af eller manglende evne til at bruge Shogun, undtagen hvor en sådan begrænsning ikke er tilladt i henhold til gældende lovgivning.",
            "disclaimer_oversight": "Menneskeligt tilsyn påkrævet: Shogun kan generere unøjagtige, ufuldstændige eller upassende outputs. Det må ikke lægges til grund uden passende menneskelig gennemgang, især i juridiske, finansielle, compliance-mæssige, sikkerhedsmæssige eller andre kontekster med stor indvirkning."
        }
    },
    "de": {
        "common": {"copyright": "© 2026 Alpha Horizon. Alle Rechte vorbehalten"},
        "guide": {
            "disclaimer_title": "Rechtlicher Haftungsausschluss",
            "disclaimer_body": "Shogun wird ausschließlich für allgemeine Informations-, experimentelle und betriebliche Zwecke bereitgestellt. Es wird „wie gesehen“ und „wie verfügbar“ bereitgestellt, ohne Garantien jeglicher Art, weder ausdrücklich noch stillschweigend, einschließlich, aber nicht beschränkt auf Genauigkeit, Eignung für einen bestimmten Zweck, Marktgängigkeit, Verfügbarkeit oder Nichtverletzung von Rechten. Die Benutzer sind allein verantwortlich für die Bewertung, Validierung, Überwachung und Genehmigung aller Ausgaben, Aktionen, Konfigurationen oder Entscheidungen, die mit oder durch Shogun getroffen werden. Alpha Horizon lehnt jede Haftung für direkte, indirekte, zufällige, Folgeschäden oder besondere Schäden ab, die aus der Nutzung oder der Unfähigkeit zur Nutzung von Shogun entstehen, es sei denn, eine solche Einschränkung ist nach geltendem Recht nicht zulässig.",
            "disclaimer_oversight": "Menschliche Aufsicht erforderlich: Shogun kann ungenaue, unvollständige oder unangemessene Ausgaben generieren. Man darf sich nicht ohne angemessene menschliche Prüfung auf Shogun verlassen, insbesondere nicht in rechtlichen, finanziellen, Compliance-, Sicherheits- oder anderen Kontexten mit hoher Auswirkung."
        }
    },
    "es": {
        "common": {"copyright": "© 2026 Alpha Horizon. Todos los derechos reservados"},
        "guide": {
            "disclaimer_title": "Aviso legal",
            "disclaimer_body": "Shogun se proporciona únicamente para uso informativo general, experimental y operativo. Se proporciona \"tal cual\" y \"según disponibilidad\", sin garantías de ningún tipo, ya sean expresas o implícitas, incluyendo, entre otras, la exactitud, la idoneidad para un propósito particular, la comerciabilidad, la disponibilidad o la no infracción. Los usuarios son los únicos responsables de evaluar, validar, monitorear y aprobar cualquier resultado, acción, configuración o decisión tomada con o a través de Shogun. Alpha Horizon renuncia a toda responsabilidad por daños directos, indirectos, incidentales, consecuentes o especiales que surjan del uso o la imposibilidad de usar Shogun, excepto cuando dicha limitación no esté permitida por la ley aplicable.",
            "disclaimer_oversight": "Se requiere supervisión humana: Shogun puede generar resultados inexactos, incompletos o inapropiados. No debe confiarse en él sin la revisión humana adecuada, especialmente en contextos legales, financieros, de cumplimiento, seguridad u otros contextos de alto impacto."
        }
    },
    "fr": {
        "common": {"copyright": "© 2026 Alpha Horizon. Tous droits réservés"},
        "guide": {
            "disclaimer_title": "Avis de non-responsabilité",
            "disclaimer_body": "Shogun est fourni uniquement à des fins d'information générale, expérimentales et opérationnelles. Il est fourni « tel quel » et « selon la disponibilité », sans garantie d'aucune sorte, expresse ou implicite, y compris, mais sans s'y limiter, l'exactitude, l'adéquation à un usage particulier, la qualité marchande, la disponibilité ou l'absence de contrefaçon. Les utilisateurs sont seuls responsables de l'évaluation, de la validation, de la surveillance et de l'approbation de toutes les sorties, actions, configurations ou décisions prises avec ou via Shogun. Alpha Horizon décline toute responsabilité pour tout dommage direct, indirect, accessoire, consécutif ou spécial découlant de l'utilisation ou de l'incapacité d'utiliser Shogun, sauf si une telle limitation n'est pas autorisée par la loi applicable.",
            "disclaimer_oversight": "Supervision humaine requise : Shogun peut générer des résultats inexacts, incomplets ou inappropriés. Il ne doit pas être utilisé sans un examen humain approprié, en particulier dans les contextes juridiques, financiers, de conformité, de sécurité ou tout autre contexte à fort impact."
        }
    },
    "it": {
        "common": {"copyright": "© 2026 Alpha Horizon. Tutti i diritti riservati"},
        "guide": {
            "disclaimer_title": "Esclusione di responsabilità legale",
            "disclaimer_body": "Shogun è fornito solo per uso informativo generale, sperimentale e operativo. Viene fornito \"così com'è\" e \"come disponibile\", senza garanzie di alcun tipo, espresse o implicite, incluse, a titolo esemplificativo, accuratezza, idoneità per uno scopo particolare, commerciabilità, disponibilità o non violazione. Gli utenti sono gli unici responsabili della valutazione, validazione, monitoraggio e approvazione di qualsiasi output, azione, configurazione o decisione presa con o tramite Shogun. Alpha Horizon declina ogni responsabilità per danni diretti, indiretti, incidentali, consequenziali o speciali derivanti dall'uso o dall'impossibilità di usare Shogun, tranne dove tale limitazione non è consentita dalla legge applicabile.",
            "disclaimer_oversight": "Supervisione umana richiesta: Shogun può generare output imprecisi, incompleti o inappropriati. Non deve essere considerato affidabile senza un'adeguata revisione umana, specialmente in contesti legali, finanziari, di conformità, sicurezza o altri contesti ad alto impatto."
        }
    },
    "ja": {
        "common": {"copyright": "© 2026 Alpha Horizon. All rights reserved"},
        "guide": {
            "disclaimer_title": "免責事項",
            "disclaimer_body": "Shogunは、一般的な情報提供、実験、および運用のためにのみ提供されます。本システムは「現状のまま」かつ「利用可能な範囲」で提供され、正確性、特定の目的への適合性、商品性、可用性、または非侵害性を含むがこれらに限定されない、明示的か黙示的かを問わず、いかなる種類の保証も行いません。ユーザーは、Shogunを使用して、またはShogunを通じて行われるすべての出力、アクション、構成、または決定を評価、検証、監視、および承認することに対して単独で責任を負います。Alpha Horizonは、適用法でそのような制限が許可されていない場合を除き、Shogunの使用または使用不能から生じる直接的、間接的、付随的、派生的、または特別な損害について一切の責任を負いません。",
            "disclaimer_oversight": "人間の監視が必要です：Shogunは、不正確、不完全、または不適切な出力を生成する可能性があります。特に法務、財務、コンプライアンス、セキュリティ、またはその他の影響の大きい文脈では、適切な人間のレビューなしに信頼しないでください。"
        }
    },
    "ko": {
        "common": {"copyright": "© 2026 Alpha Horizon. All rights reserved"},
        "guide": {
            "disclaimer_title": "법적 고지",
            "disclaimer_body": "Shogun은 일반적인 정보 제공, 실험 및 운영 목적으로만 제공됩니다. 정확성, 특정 목적에의 적합성, 상업성, 가용성 또는 비침해성을 포함하되 이에 국한되지 않는 명시적 또는 묵시적인 어떠한 종류의 보증 없이 \"있는 그대로\" 및 \"이용 가능한 대로\" 제공됩니다. 사용자는 Shogun을 사용하거나 Shogun을 통해 이루어진 모든 출력물, 작업, 설정 또는 결정 사항을 평가, 검증, 모니터링 및 승인할 전적인 책임이 있습니다. Alpha Horizon은 관련 법률에 의해 그러한 제한이 허용되지 않는 경우를 제외하고 Shogun의 사용 또는 사용 불능으로 인해 발생하는 직접적, 간접적, 부수적, 결과적 또는 특별한 손해에 대해 어떠한 책임도 지지 않습니다.",
            "disclaimer_oversight": "인간의 감독 필요: Shogun은 부정확하거나 불완전하거나 부적절한 출력물을 생성할 수 있습니다. 특히 법률, 재무, 규정 준수, 보안 또는 기타 영향이 큰 상황에서는 적절한 인간의 검토 없이 의존해서는 안 됩니다."
        }
    },
    "no": {
        "common": {"copyright": "© 2026 Alpha Horizon. Med enerett"},
        "guide": {
            "disclaimer_title": "Juridisk ansvarsfraskrivelse",
            "disclaimer_body": "Shogun leveres kun for generell informasjonsmessig, eksperimentell og operasjonell bruk. Den leveres \"som den er\" og \"som tilgjengelig\", uten garantier av noe slag, verken uttrykkelige eller underforståtte, inkludert, men ikke begrenset til, nøyaktighet, egnethet for et bestemt formål, salgbarhet, tilgjengelighet eller ikke-krenkelse. Brukere er selv ansvarlige for å evaluere, validere, overvåke og godkjenne alle resultater, handlinger, konfigurasjoner eller beslutninger som tas med eller gjennom Shogun. Alpha Horizon fraskriver seg ethvert ansvar for direkte, indirekte, tilfeldige, følgeskader eller spesielle skader som oppstår som følge af bruk av, eller manglende evne til å bruke, Shogun, unntatt der en slik begrensning ikke er tillatt i henhold til gjeldende lov.",
            "disclaimer_oversight": "Menneskelig tilsyn påkrevd: Shogun kan generere unøyaktige, ufullstendige eller upassende resultater. Det må ikke stoles på uten passende menneskelig vurdering, spesielt i juridiske, finansielle, compliance-, sikkerhets- eller andre høyrisikokontekster."
        }
    },
    "pl": {
        "common": {"copyright": "© 2026 Alpha Horizon. Wszelkie prawa zastrzeżone"},
        "guide": {
            "disclaimer_title": "Zastrzeżenia prawne",
            "disclaimer_body": "Shogun jest udostępniany wyłącznie do ogólnych celów informacyjnych, eksperymentalnych i operacyjnych. Jest dostarczany w stanie, w jakim się znajduje („as is”), i w miarę dostępności („as available”), bez jakichkolwiek gwarancji, wyraźnych lub dorozumianych, w tym m.in. gwarancji dokładności, przydatności do określonego celu, wartości handlowej, dostępności lub nienaruszania praw osób trzecich. Użytkownicy ponoszą wyłączną odpowiedzialność za ocenę, walidację, monitorowanie i zatwierdzanie wszelkich wyników, działań, konfiguracji lub decyzji podejmowanych za pomocą lub za pośrednictwem systemu Shogun. Alpha Horizon zrzeka się wszelkiej odpowiedzialności za jakiekolwiek szkody bezpośrednie, pośrednie, przypadkowe, wtórne lub szczególne wynikające z korzystania lub niemożności korzystania z systemu Shogun, z wyjątkiem sytuacji, w których takie ograniczenie nie jest dozwolone przez obowiązujące prawo.",
            "disclaimer_oversight": "Wymagany nadzór człowieka: Shogun może generować niedokładne, niepełne lub niewłaściwe wyniki. Nie należy na nim polegać bez odpowiedniej weryfikacji przez człowieka, szczególnie w kontekstach prawnych, finansowych, związanych ze zgodnością, bezpieczeństwem lub innych obszarach o wysokim stopniu ryzyka."
        }
    },
    "pt": {
        "common": {"copyright": "© 2026 Alpha Horizon. Todos os direitos reservados"},
        "guide": {
            "disclaimer_title": "Aviso Legal",
            "disclaimer_body": "O Shogun é fornecido apenas para uso informativo geral, experimental e operacional. É fornecido \"como está\" e \"conforme disponível\", sem garantias de qualquer tipo, expressas ou implícitas, incluindo, entre outras, precisão, adequação a um propósito específico, comercialização, disponibilidade ou não violação. Os usuários são os únicos responsáveis por avaliar, validar, monitorar e aprovar quaisquer saídas, ações, configurações ou decisões tomadas com ou por meio do Shogun. A Alpha Horizon isenta-se de responsabilidade por quaisquer danos diretos, indiretos, incidentais, consequenciais ou especiais decorrentes do uso ou da incapacidade de usar o Shogun, exceto onde tal limitação não for permitida pela lei aplicável.",
            "disclaimer_oversight": "Supervisão humana necessária: O Shogun pode gerar saídas imprecisas, incompletas ou inadequadas. Não deve ser invocado sem a revisão humana adequada, especialmente em contextos legais, financeiros, de conformidade, segurança ou outros contextos de alto impacto."
        }
    },
    "sv": {
        "common": {"copyright": "© 2026 Alpha Horizon. Med ensamrätt"},
        "guide": {
            "disclaimer_title": "Juridisk ansvarsfriskrivning",
            "disclaimer_body": "Shogun tillhandahålls endast för allmän informativ, experimentell och operativ användning. Den tillhandahålls i \"befintligt skick\" och \"i mån av tillgång\", utan några garantier av något slag, vare sig uttryckliga eller underförstådda, inklusive men inte begränsat till noggrannhet, lämplighet för ett visst ändamål, säljbarhet, tillgänglighet eller icke-intrång. Användare är ensamma ansvariga för att utvärdera, validera, övervaka och godkänna alla utdata, åtgärder, konfigurationer eller beslut som fattas med eller genom Shogun. Alpha Horizon frånsäger sig allt ansvar för direkta, indirekta, tillfälliga, följdskador eller särskilda skador som uppstår till följd av användning av, eller oförmåga att använda, Shogun, förutom där en sådan begränsning inte är tillåten enligt tillämplig lag.",
            "disclaimer_oversight": "Mänsklig tillsyn krävs: Shogun kan generera felaktiga, ofullständiga eller olämpliga utdata. Man bör inte förlita sig på den utan lämplig mänsklig granskning, särskilt i juridiska, finansiella, efterlevnads-, säkerhets- eller andra sammanhang med stor inverkan."
        }
    },
    "uk": {
        "common": {"copyright": "© 2026 Alpha Horizon. Усі права захищено"},
        "guide": {
            "disclaimer_title": "Відмова від відповідальності",
            "disclaimer_body": "Shogun надається виключно для загального інформаційного, експериментального та операційного використання. Він надається на умовах «як є» та «за наявності», без будь-яких гарантій, явних або неявних, включаючи, але не обмежуючись, точністю, придатністю для певної мети, товарною придатністю, доступністю або непорушенням прав. Користувачі несуть одноосібну відповідальність за оцінку, перевірку, моніторинг та схвалення будь-яких результатів, дій, конфігурацій або рішень, прийнятих за допомогою Shogun. Alpha Horizon не несе відповідальності за будь-які прямі, непрямі, випадкові, непрямі або спеціальні збитки, що виникають внаслідок використання або неможливості використання Shogun, за винятком випадків, коли таке обмеження не передбачено чинним законодавством.",
            "disclaimer_oversight": "Необхідний нагляд людини: Shogun може генерувати неточні, неповні або неналежні результати. На нього не слід покладатися без належного контролю з боку людини, особливо в юридичних, фінансових, безпекових контекстах, а також у сферах комплаєнсу або інших сферах з високим рівнем впливу."
        }
    },
    "zh": {
        "common": {"copyright": "© 2026 Alpha Horizon. 保留所有权利"},
        "guide": {
            "disclaimer_title": "法律免责声明",
            "disclaimer_body": "Shogun 仅供一般的资讯、实验和运营使用。它按“现状”和“可用性”提供，不提供任何形式的明示或暗示保证，包括但不限于准确性、特定用途的适用性、适销性、可用性或非侵权性。用户全权负责评估、验证、监督和批准通过 Shogun 做出或进行的任何输出、行动、配置或决策。Alpha Horizon 对因使用或无法使用 Shogun 而引起的任何直接、间接、附带、后果性或特殊损害不承担任何责任，除非适用法律不允许此类限制。",
            "disclaimer_oversight": "需要人工监督：Shogun 可能会产生不准确、不完整或不恰当的输出。在没有适当的人工审查的情况下，不得依赖它，特别是在法律、财务、合规、安全或其他高影响的背景下。"
        }
    }
}

i18n_dir = r"c:\Users\mdper\Documents\Projekter\Shogun\frontend\src\i18n"

for lang, content in translations.items():
    file_path = os.path.join(i18n_dir, f"{lang}.json")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Update common.copyright
        if "common" in data:
            data["common"]["copyright"] = content["common"]["copyright"]
        
        # Update guide disclaimer
        if "guide" in data:
            data["guide"].update(content["guide"])
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
print("Disclaimer translations applied to all language files.")
