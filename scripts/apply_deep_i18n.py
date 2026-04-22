import json
import os

langs = {
    "da": "Danish", "de": "German", "es": "Spanish", "fr": "French", 
    "it": "Italian", "ja": "Japanese", "ko": "Korean", "no": "Norwegian", 
    "pl": "Polish", "pt": "Portuguese", "sv": "Swedish", "uk": "Ukrainian", "zh": "Chinese"
}

# The translations mapped manually by AI to save API tokens
translations = {
    # Dashboard updates
    "dashboard": {
        "active_deployment": {"da": "Aktivt Implementeringsregister", "de": "Aktives Bereitstellungsregister", "es": "Registro de Despliegue Activo", "fr": "Registre de Déploiement Actif", "it": "Registro di Distribuzione Attivo", "ja": "アクティブ展開レジストリ", "ko": "활성 배포 레지스트리", "no": "Aktivt Implementeringsregister", "pl": "Aktywny Rejestr Wdrożeń", "pt": "Registro de Implantação Ativo", "sv": "Aktivt Implementeringsregister", "uk": "Реєстр активного розгортання", "zh": "活动部署注册表"},
        "full_fleet": {"da": "Fuld Flåde", "de": "Gesamte Flotte", "es": "Flota Completa", "fr": "Flotte Complète", "it": "Flotta Completa", "ja": "全フリート", "ko": "전체 함대", "no": "Full Flåte", "pl": "Pełna Flota", "pt": "Frota Completa", "sv": "Full Flotta", "uk": "Повний флот", "zh": "整个机队"},
        "designation": {"da": "Betegnelse", "de": "Bezeichnung", "es": "Designación", "fr": "Désignation", "it": "Designazione", "ja": "名称", "ko": "지정", "no": "Betegnelse", "pl": "Oznaczenie", "pt": "Designação", "sv": "Beteckning", "uk": "Позначення", "zh": "名称"},
        "current_task": {"da": "Nuværende Opgave", "de": "Aktuelle Aufgabe", "es": "Tarea Actual", "fr": "Tâche Actuelle", "it": "Attività Corrente", "ja": "現在のタスク", "ko": "현재 작업", "no": "Nåværende Oppgave", "pl": "Bieżące Zadanie", "pt": "Tarefa Atual", "sv": "Nuvarande Uppgift", "uk": "Поточне завдання", "zh": "当前任务"},
        "engagement": {"da": "Engagement", "de": "Beteiligung", "es": "Compromiso", "fr": "Engagement", "it": "Impegno", "ja": "関与", "ko": "참여", "no": "Engasjement", "pl": "Zaangażowanie", "pt": "Engajamento", "sv": "Engagemang", "uk": "Залучення", "zh": "参与度"},
        "status": {"da": "Status", "de": "Status", "es": "Estado", "fr": "Statut", "it": "Stato", "ja": "ステータス", "ko": "상태", "no": "Status", "pl": "Status", "pt": "Status", "sv": "Status", "uk": "Статус", "zh": "状态"}
    },
    
    # Katana updates
    "katana": {
        "provider": {"da": "Udbyder", "de": "Anbieter", "es": "Proveedor", "fr": "Fournisseur", "it": "Fornitore", "ja": "プロバイダー", "ko": "공급자", "no": "Leverandør", "pl": "Dostawca", "pt": "Provedor", "sv": "Leverantör", "uk": "Провайдер", "zh": "提供商"},
        "auth_type": {"da": "Godkendelsestype", "de": "Authentifizierungstyp", "es": "Tipo de Autenticación", "fr": "Type d'Authentification", "it": "Tipo di Autenticazione", "ja": "認証タイプ", "ko": "인증 유형", "no": "Autentiseringstype", "pl": "Typ uwierzytelnienia", "pt": "Tipo de Autenticação", "sv": "Autentiseringstyp", "uk": "Тип автентифікації", "zh": "身份验证类型"},
        "display_name": {"da": "Visningsnavn", "de": "Anzeigename", "es": "Nombre para Mostrar", "fr": "Nom d'affichage", "it": "Nome da visualizzare", "ja": "表示名", "ko": "표시 이름", "no": "Visningsnavn", "pl": "Nazwa wyświetlana", "pt": "Nome de Exibição", "sv": "Visningsnamn", "uk": "Відображуване ім'я", "zh": "显示名称"},
        "api_key": {"da": "API-Nøgle", "de": "API-Schlüssel", "es": "Clave API", "fr": "Clé API", "it": "Chiave API", "ja": "APIキー", "ko": "API 키", "no": "API-Nøkkel", "pl": "Klucz API", "pt": "Chave API", "sv": "API-Nyckel", "uk": "Ключ API", "zh": "API 密钥"},
        "custom_model_tag": {"da": "Brugerdefineret Model-Tag", "de": "Benutzerdefiniertes Modell-Tag", "es": "Etiqueta de Modelo Personalizada", "fr": "Balise de modèle personnalisée", "it": "Tag modello personalizzato", "ja": "カスタムモデルタグ", "ko": "사용자 지정 모델 태그", "no": "Egendefinert modell-tag", "pl": "Niestandardowy tag modelu", "pt": "Tag de Modelo Personalizada", "sv": "Anpassad modelltagg", "uk": "Спеціальний тег моделі", "zh": "自定义模型标签"},
        "tool_name": {"da": "Værktøjsnavn *", "de": "Werkzeugname *", "es": "Nombre de Herramienta *", "fr": "Nom de l'outil *", "it": "Nome dello strumento *", "ja": "ツール名 *", "ko": "도구 이름 *", "no": "Verktøynavn *", "pl": "Nazwa narzędzia *", "pt": "Nome da Ferramenta *", "sv": "Verktygsnamn *", "uk": "Назва інструменту *", "zh": "工具名称 *"},
        "slug": {"da": "Slug *", "de": "Slug *", "es": "Slug *", "fr": "Slug *", "it": "Slug *", "ja": "Slug *", "ko": "슬러그 *", "no": "Slug *", "pl": "Slug *", "pt": "Slug *", "sv": "Slug *", "uk": "Слаг *", "zh": "Slug *"},
        "base_url": {"da": "Basis URL", "de": "Basis-URL", "es": "URL Base", "fr": "URL de base", "it": "URL di base", "ja": "ベースURL", "ko": "기본 URL", "no": "Basis URL", "pl": "Bazowy adres URL", "pt": "URL Base", "sv": "Bas-URL", "uk": "Базова URL", "zh": "基础 URL"},
        "connector_type": {"da": "Konnektortype", "de": "Konnektortyp", "es": "Tipo de Conector", "fr": "Type de Connecteur", "it": "Tipo di connettore", "ja": "コネクタタイプ", "ko": "커넥터 유형", "no": "Konnektortype", "pl": "Typ złącza", "pt": "Tipo de Conector", "sv": "Kontakttyp", "uk": "Тип роз'єму", "zh": "连接器类型"},
        "risk_level": {"da": "Risikoniveau", "de": "Risikostufe", "es": "Nivel de riesgo", "fr": "Niveau de risque", "it": "Livello di rischio", "ja": "リスクレベル", "ko": "위험 수준", "no": "Risikonivå", "pl": "Poziom ryzyka", "pt": "Nível de risco", "sv": "Risknivå", "uk": "Рівень ризику", "zh": "风险级别"},
        "profile_name": {"da": "Profilnavn *", "de": "Profilname *", "es": "Nombre de perfil *", "fr": "Nom du profil *", "it": "Nome del profilo *", "ja": "プロファイル名 *", "ko": "프로필 이름 *", "no": "Profilnavn *", "pl": "Nazwa profilu *", "pt": "Nome do Perfil *", "sv": "Profilnamn *", "uk": "Назва профілю *", "zh": "配置名称 *"},
        "description": {"da": "Beskrivelse", "de": "Beschreibung", "es": "Descripción", "fr": "Description", "it": "Descrizione", "ja": "説明", "ko": "설명", "no": "Beskrivelse", "pl": "Opis", "pt": "Descrição", "sv": "Beskrivning", "uk": "Опис", "zh": "描述"},
        "task_type": {"da": "Opgavetype", "de": "Aufgabentyp", "es": "Tipo de Tarea", "fr": "Type de Tâche", "it": "Tipo di attività", "ja": "タスクタイプ", "ko": "작업 유형", "no": "Oppgavetype", "pl": "Typ zadania", "pt": "Tipo de Tarefa", "sv": "Uppgiftstyp", "uk": "Тип завдання", "zh": "任务类型"},
        "primary_model_provider": {"da": "Primær Modeludbyder *", "de": "Primärer Modellanbieter *", "es": "Proveedor de Modelo Principal *", "fr": "Fournisseur de modèle principal *", "it": "Fornitore modello principale *", "ja": "プライマリモデルプロバイダー *", "ko": "주요 모델 제공자 *", "no": "Primær modellleverandør *", "pl": "Główny dostawca modelu *", "pt": "Provedor de Modelo Principal *", "sv": "Primär modellleverantör *", "uk": "Основний провайдер моделі *", "zh": "主要模型提供商 *"},
        "latency_bias": {"da": "Latensbias", "de": "Latenz-Tendenz", "es": "Sesgo de latencia", "fr": "Biais de latence", "it": "Inclinazione della Latenza", "ja": "レイテンシバイアス", "ko": "대기 시간 편향", "no": "Latensbias", "pl": "Stronniczość opóźnienia", "pt": "Viés de Latência", "sv": "Latensförspänning", "uk": "Схильність до затримки", "zh": "延迟偏好"},
        "cost_bias": {"da": "Omkostningsbias", "de": "Kosten-Tendenz", "es": "Sesgo de costo", "fr": "Biais de coût", "it": "Inclinazione dei costi", "ja": "コストバイアス", "ko": "비용 편향", "no": "Kostnadsbias", "pl": "Stronniczość kosztów", "pt": "Viés de Custo", "sv": "Kostnadsförspänning", "uk": "Схильність до витрат", "zh": "成本偏好"},
        "update_mode": {"da": "Opdateringstilstand", "de": "Aktualisierungsmodus", "es": "Modo de actualización", "fr": "Mode de mise à jour", "it": "Modalità di aggiornamento", "ja": "更新モード", "ko": "업데이트 모드", "no": "Oppdateringsmodus", "pl": "Tryb aktualizacji", "pt": "Modo de Atualização", "sv": "Uppdateringsläge", "uk": "Режим оновлення", "zh": "更新模式"},
        "webhook_url": {"da": "Webhook URL *", "de": "Webhook-URL *", "es": "URL de Webhook *", "fr": "URL du webhook *", "it": "URL webhook *", "ja": "Webhook URL *", "ko": "Webhook URL *", "no": "Webhook URL *", "pl": "Adres URL pętli *", "pt": "URL do Webhook *", "sv": "Webhook URL *", "uk": "URL-адреса веб-хука *", "zh": "Webhook URL *"}
    },
    
    # Samurai Network / Tables Updates
    "samurai": {
        "table_designation": {"da": "Betegnelse", "de": "Bezeichnung", "es": "Designación", "fr": "Désignation", "it": "Designazione", "ja": "名称", "ko": "지정", "no": "Betegnelse", "pl": "Oznaczenie", "pt": "Designação", "sv": "Beteckning", "uk": "Позначення", "zh": "名称"},
        "table_status": {"da": "Status", "de": "Status", "es": "Estado", "fr": "Statut", "it": "Stato", "ja": "ステータス", "ko": "상태", "no": "Status", "pl": "Status", "pt": "Status", "sv": "Status", "uk": "Статус", "zh": "状态"},
        "table_task": {"da": "Nuværende Opgave", "de": "Aktuelle Aufgabe", "es": "Tarea Actual", "fr": "Tâche Actuelle", "it": "Attività Corrente", "ja": "現在のタスク", "ko": "현재 작업", "no": "Nåværende Oppgave", "pl": "Bieżące Zadanie", "pt": "Tarefa Atual", "sv": "Nuvarande Uppgift", "uk": "Поточне завдання", "zh": "当前任务"},
        "table_role": {"da": "Rolle / Slug", "de": "Rolle / Slug", "es": "Rol / Slug", "fr": "Rôle / Slug", "it": "Ruolo / Slug", "ja": "ロール / Slug", "ko": "역할 / 슬러그", "no": "Rolle / Slug", "pl": "Rola / Slug", "pt": "Papel / Slug", "sv": "Roll / Slug", "uk": "Роль / Слаг", "zh": "角色 / Slug"},
        "table_routing": {"da": "Routing", "de": "Routing", "es": "Enrutamiento", "fr": "Routage", "it": "Instradamento", "ja": "ルーティング", "ko": "라우팅", "no": "Ruting", "pl": "Routing", "pt": "Roteamento", "sv": "Ruttning", "uk": "Маршрутизація", "zh": "路由"},
        "table_deployed": {"da": "Implementeret Den", "de": "Bereitgestellt am", "es": "Desplegado a las", "fr": "Déployé le", "it": "Distribuito il", "ja": "展開日", "ko": "배포 날짜", "no": "Distribuert den", "pl": "Wdrożono dnia", "pt": "Implantado em", "sv": "Gjennomfört den", "uk": "Розгорнуто", "zh": "部署于"}
    },
    
    # Archives updates
    "archives": {
        "memory_type": {"da": "Hukommelsestype", "de": "Speichertyp", "es": "Tipo de Memoria", "fr": "Type de mémoire", "it": "Tipo di Memoria", "ja": "メモリタイプ", "ko": "메모리 유형", "no": "Hukommelsestype", "pl": "Typ pamięci", "pt": "Tipo de Memória", "sv": "Minnetyp", "uk": "Тип пам'яті", "zh": "记忆类型"},
        "agent_attribution": {"da": "Agent-tilskrivning", "de": "Agentzuordnung", "es": "Atribución de Agente", "fr": "Attribution d'agent", "it": "Attribuzione Agente", "ja": "エージェントの帰属", "ko": "에이전트 속성", "no": "Agent-attribusjon", "pl": "Atrybucja agenta", "pt": "Atribuição de Agente", "sv": "Agenttilldelning", "uk": "Атрибуція агента", "zh": "代理归属"},
        "memory_title": {"da": "Hukommelsestitel", "de": "Speichertitel", "es": "Título de Memoria", "fr": "Titre de la Mémoire", "it": "Titolo della Memoria", "ja": "メモリタイトル", "ko": "메모리 제목", "no": "Minnetittel", "pl": "Tytuł Pamięci", "pt": "Título de Memória", "sv": "Minnetitel", "uk": "Назва пам'яті", "zh": "记忆标题"},
        "content_payload": {"da": "Indholdsnyttelast", "de": "Inhaltliche Nutzlast", "es": "Carga de Contenido", "fr": "Charge utile du contenu", "it": "Carico del Contenuto", "ja": "コンテンツペイロード", "ko": "콘텐츠 페이로드", "no": "Innholdspayload", "pl": "Ładunek Zawartości", "pt": "Carga de Conteúdo", "sv": "Innehållslast", "uk": "Зміст навантаження", "zh": "内容负载"},
        "decay_class": {"da": "Nedbrydningsklasse", "de": "Zerfallsklasse", "es": "Clase de Decaimiento", "fr": "Classe de décroissance", "it": "Classe di Deperimento", "ja": "崩壊クラス", "ko": "감쇠 등급", "no": "Nedbrytningsklasse", "pl": "Klasa Rozkładu", "pt": "Classe de Decaimento", "sv": "Sönderfallsklass", "uk": "Клас розпаду", "zh": "衰减等级"}
    },
    
    # Profile / Torii labels
    "profile": {
        "agent_name": {"da": "Agentnavn", "de": "Agentenname", "es": "Nombre de Agente", "fr": "Nom de l'Agent", "it": "Nome Agente", "ja": "エージェント名", "ko": "에이전트 이름", "no": "Agentnavn", "pl": "Nazwa Agenta", "pt": "Nome do Agente", "sv": "Agentnamn", "uk": "Ім'я агента", "zh": "代理名称"},
        "active_persona": {"da": "Aktiv Persona", "de": "Aktive Persona", "es": "Persona Activa", "fr": "Persona Active", "it": "Persona Attiva", "ja": "アクティブペルソナ", "ko": "활성 페르소나", "no": "Aktiv Persona", "pl": "Aktywna Persona", "pt": "Persona Ativa", "sv": "Aktiv Persona", "uk": "Активна персона", "zh": "活动角色"},
        "description": {"da": "Beskrivelse", "de": "Beschreibung", "es": "Descripción", "fr": "Description", "it": "Descrizione", "ja": "説明", "ko": "설명", "no": "Beskrivelse", "pl": "Opis", "pt": "Descrição", "sv": "Beskrivning", "uk": "Опис", "zh": "描述"},
        "autonomy_level": {"da": "Autonomieniveau", "de": "Autonomiestufe", "es": "Nivel de Autonomía", "fr": "Niveau d'Autonomie", "it": "Livello di Autonomia", "ja": "自律性レベル", "ko": "자율성 수준", "no": "Autonominivå", "pl": "Poziom Autonomii", "pt": "Nível de Autonomia", "sv": "Autonominivå", "uk": "Рівень автономії", "zh": "自治级别"},
        "select_model": {"da": "Vælg Model", "de": "Modell Auswählen", "es": "Seleccionar Modelo", "fr": "Sélectionner Modèle", "it": "Seleziona Modello", "ja": "モデルの選択", "ko": "모델 선택", "no": "Velg Modell", "pl": "Wybierz Model", "pt": "Selecionar Modelo", "sv": "Välj Modell", "uk": "Виберіть модель", "zh": "选择模型"},
        "add_fallback": {"da": "Tilføj Fallback", "de": "Fallback Hinzufügen", "es": "Añadir Respaldo", "fr": "Ajouter un Secours", "it": "Aggiungi Riserva", "ja": "フォールバックの追加", "ko": "대체 추가", "no": "Legg til Fallback", "pl": "Dodaj Zabezpieczenie", "pt": "Adicionar Fallback", "sv": "Lägg till Fallback", "uk": "Додати резервний варіант", "zh": "添加回退"},
        "fallback_order": {"da": "Fallback-rækkefølge", "de": "Fallback-Reihenfolge", "es": "Orden de Respaldo", "fr": "Ordre de Secours", "it": "Ordine di Riserva", "ja": "フォールバック順序", "ko": "대체 순서", "no": "Fallback-rekkefølge", "pl": "Kolejność Zabezpieczeń", "pt": "Ordem de Fallback", "sv": "Fallback-ordning", "uk": "Порядок резервного копіювання", "zh": "回退顺序"},
        "routing_strategy": {"da": "Routing-strategi", "de": "Routing-Strategie", "es": "Estrategia de Enrutamiento", "fr": "Stratégie de Routage", "it": "Strategia di Instradamento", "ja": "ルーティング戦略", "ko": "라우팅 전략", "no": "Routingstrategi", "pl": "Strategia Routingu", "pt": "Estratégia de Roteamento", "sv": "Routingstrategi", "uk": "Стратегія маршрутизації", "zh": "路由策略"},
        "base_policy": {"da": "Grundpolitik", "de": "Basisrichtlinie", "es": "Política Base", "fr": "Politique de Base", "it": "Politica di Base", "ja": "ベースポリシー", "ko": "기본 정책", "no": "Grunnpolitikk", "pl": "Polityka Bazowa", "pt": "Política Base", "sv": "Grundpolicy", "uk": "Базова політика", "zh": "基本政策"},
        "custom_policy_name": {"da": "Brugerdefineret Politiknavn", "de": "Benutzerdefinierter Richtlinienname", "es": "Nombre de Política Personalizado", "fr": "Nom de Politique Personnalisé", "it": "Nome Politica Personalizzata", "ja": "カスタムポリシー名", "ko": "사용자 지정 정책 이름", "no": "Egendefinert Politiknavn", "pl": "Niestandardowa Nazwa Polityki", "pt": "Nome de Política Personalizado", "sv": "Anpassat Policynamn", "uk": "Назва спеціальної політики", "zh": "自定义策略名称"},
        "job_name": {"da": "Jobnavn", "de": "Jobname", "es": "Nombre del Trabajo", "fr": "Nom du Travail", "it": "Nome Lavoro", "ja": "ジョブ名", "ko": "작업 이름", "no": "Jobbnavn", "pl": "Nazwa Zadania", "pt": "Nome do Trabalho", "sv": "Jobbnamn", "uk": "Назва роботи", "zh": "任务名称"},
        "job_type": {"da": "Jobtype", "de": "Jobtyp", "es": "Tipo de Trabajo", "fr": "Type de Travail", "it": "Tipo Lavoro", "ja": "ジョブタイプ", "ko": "작업 유형", "no": "Jobbtype", "pl": "Typ Zadania", "pt": "Tipo do Trabalho", "sv": "Jobbtyp", "uk": "Тип роботи", "zh": "任务类型"},
        "frequency": {"da": "Frekvens", "de": "Häufigkeit", "es": "Frecuencia", "fr": "Fréquence", "it": "Frequenza", "ja": "頻度", "ko": "빈도", "no": "Frekvens", "pl": "Częstotliwość", "pt": "Frequência", "sv": "Frekvens", "uk": "Частота", "zh": "频率"},
        "priority": {"da": "Prioritet", "de": "Priorität", "es": "Prioridad", "fr": "Priorité", "it": "Priorità", "ja": "優先度", "ko": "우선순위", "no": "Prioritet", "pl": "Priorytet", "pt": "Prioridade", "sv": "Prioritet", "uk": "Пріоритет", "zh": "优先级"},
        "task_instruction": {"da": "Opgaveinstruktion", "de": "Aufgabenanweisung", "es": "Instrucción de Tarea", "fr": "Instruction Tâche", "it": "Istruzione Attività", "ja": "タスクの指示", "ko": "작업 지시", "no": "Oppgaveinstruksjon", "pl": "Instrukcja Zadania", "pt": "Instrução de Tarefa", "sv": "Uppgiftsinstruktion", "uk": "Інструкція щодо завдання", "zh": "任务说明"},
        "options": {"da": "Valgmuligheder", "de": "Optionen", "es": "Opciones", "fr": "Options", "it": "Opzioni", "ja": "オプション", "ko": "옵션", "no": "Alternativer", "pl": "Opcje", "pt": "Opções", "sv": "Alternativ", "uk": "Параметри", "zh": "选项"},
    },
    
    "torii": {
        "policy_name": {"da": "Politiknavn *", "de": "Richtlinienname *", "es": "Nombre de Política *", "fr": "Nom de Politique *", "it": "Nome Politica *", "ja": "ポリシー名 *", "ko": "정책 이름 *", "no": "Politiknavn *", "pl": "Nazwa Polityki *", "pt": "Nome da Política *", "sv": "Policynamn *", "uk": "Назва політики *", "zh": "策略名称 *"},
        "security_tier": {"da": "Sikkerhedsniveau *", "de": "Sicherheitsstufe *", "es": "Nivel de Seguridad *", "fr": "Niveau de Sécurité *", "it": "Livello di Sicurezza *", "ja": "セキュリティ層 *", "ko": "보안 계층 *", "no": "Sikkerhetsnivå *", "pl": "Poziom Bezpieczeństwa *", "pt": "Nível de Segurança *", "sv": "Säkerhetsnivå *", "uk": "Рівень безпеки *", "zh": "安全层 *"},
        "description": {"da": "Beskrivelse", "de": "Beschreibung", "es": "Descripción", "fr": "Description", "it": "Descrizione", "ja": "説明", "ko": "설명", "no": "Beskrivelse", "pl": "Opis", "pt": "Descrição", "sv": "Beskrivning", "uk": "Опис", "zh": "描述"}
    }
}

i18n_dir = "frontend/src/i18n"

for lang in langs.keys():
    file_path = os.path.join(i18n_dir, f"{lang}.json")
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf8') as f:
            data = json.load(f)
            
        for namespace, keys in translations.items():
            if namespace not in data:
                data[namespace] = {}
            for key, l_map in keys.items():
                if lang in l_map:
                    # Update ONLY with correct mapped string (fallback to english if something went wrong)
                    data[namespace][key] = l_map[lang]
        
        with open(file_path, 'w', encoding='utf8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

print("Comprehensive translation manifest applied to all 13 external JSON files!")
