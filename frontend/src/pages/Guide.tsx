import { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  Archive,
  BookOpen,
  Clock,
  Cpu,
  Info,
  ShieldCheck,
  SlidersHorizontal,
  Workflow,
} from 'lucide-react';
import { useLocation } from 'react-router-dom';
import {
  requestedGuideSection,
  requestedGuideTab,
  type GuideTab,
} from '../lib/guideNavigation';

const guideSections = [
  {
    title: 'Start with Shogun Profile',
    icon: Cpu,
    body: 'Choose the primary model route, personality, mandate, memory behavior, and operating preferences for your single-user installation.',
  },
  {
    title: 'Connect tools in Katana',
    icon: SlidersHorizontal,
    body: 'Configure model providers, Telegram, email, calendar, and other supported local integrations. Keep credentials in the encrypted vault.',
  },
  {
    title: 'Build AgentFlows',
    icon: Workflow,
    body: 'Create visual workflows with inputs, Samurai workers, conditions, approvals, browser actions, document tools, outputs, and Telegram delivery.',
  },
  {
    title: 'Control permissions',
    icon: ShieldCheck,
    body: 'Use Torii and ToolGate to select a posture, limit capabilities, review high-risk actions, and activate HARAKIRI when governed work must stop.',
  },
  {
    title: 'Use Archives and Dojo',
    icon: Archive,
    body: 'Review persistent memory, install appropriate skills, and keep human oversight over retrieved context and generated output.',
  },
  {
    title: 'Automate carefully',
    icon: Clock,
    body: 'Test AgentFlows manually before activation, verify external delivery, keep backups, and inspect errors directly in the relevant workflow or system surface.',
  },
];

export function Guide() {
  const location = useLocation();
  const [activeTab, setActiveTab] = useState<GuideTab>(
    () => requestedGuideTab(location.search) ?? 'onboarding',
  );
  const REFERENCE_SECTIONS = useMemo(() => [
    { id: 'ref-maintenance', label: 'Maintenance & Privacy' },
    { id: 'ref-roles-responsibilities', label: 'Roles & Responsibilities' },
    { id: 'ref-modified-installations', label: 'Modified Installations' },
    { id: 'ref-incident-reporting', label: 'Incident Reporting' },
  ], []);

  useEffect(() => {
    const tab = requestedGuideTab(location.search);
    if (tab) setActiveTab(tab);
    const section = requestedGuideSection(
      location.hash,
      REFERENCE_SECTIONS.map(({ id }) => id),
    );
    if (section) {
      setActiveTab('reference');
      window.requestAnimationFrame(() => document.getElementById(section)?.scrollIntoView());
    }
  }, [location.hash, location.search, REFERENCE_SECTIONS]);

  return (
    <div className="min-h-screen bg-shogun-bg p-6 md:p-10">
      <div className="mx-auto max-w-5xl space-y-8">
        <header className="space-y-5 border-b border-shogun-border pb-7">
          <div className="flex items-center gap-3">
            <div className="rounded-xl border border-shogun-gold/30 bg-shogun-gold/10 p-3">
              <BookOpen className="h-6 w-6 text-shogun-gold" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-shogun-text">Yellow Label Guide</h1>
              <p className="text-sm text-shogun-subdued">Set up, govern, and operate your local Shogun.</p>
            </div>
          </div>
          <nav className="flex flex-wrap gap-2" aria-label="Guide sections">
            {(['onboarding', 'reference', 'architecture', 'safety'] as GuideTab[]).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={`rounded-lg border px-3 py-2 text-xs font-bold capitalize ${activeTab === tab ? 'border-shogun-gold/40 bg-shogun-gold/10 text-shogun-gold' : 'border-shogun-border text-shogun-subdued'}`}
              >
                {tab}
              </button>
            ))}
          </nav>
        </header>

        {activeTab === 'onboarding' && (
          <div className="space-y-6">
            <section className="grid gap-4 md:grid-cols-2">
              {guideSections.map(({ title, icon: Icon, body }) => (
                <article key={title} className="shogun-card space-y-3">
                  <div className="flex items-center gap-2 font-bold text-shogun-text">
                    <Icon className="h-4 w-4 text-shogun-gold" />
                    {title}
                  </div>
                  <p className="text-xs leading-relaxed text-shogun-subdued">{body}</p>
                </article>
              ))}
            </section>
            <section className="shogun-card border-shogun-blue/30 bg-shogun-blue/5">
              <div className="flex items-start gap-3">
                <Info className="mt-0.5 h-5 w-5 shrink-0 text-shogun-blue" />
                <div className="space-y-2">
                  <h2 className="text-sm font-bold text-shogun-text">Existing installation data</h2>
                  <p className="text-xs leading-relaxed text-shogun-subdued">
                    Yellow Label does not expose commercial-edition features. Upgrading an existing installation does not intentionally delete their saved records, so an authorized future White Label upgrade can migrate or restore them.
                  </p>
                </div>
              </div>
            </section>
          </div>
        )}

        {activeTab === 'reference' && (
          <div className="space-y-6">
            <nav className="flex flex-wrap gap-2" aria-label="Reference sections">
              {REFERENCE_SECTIONS.map(({ id, label }) => (
                <a key={id} href={`#${id}`} className="text-xs text-shogun-blue hover:text-shogun-gold">{label}</a>
              ))}
            </nav>

            <section id="ref-maintenance" className="shogun-card space-y-3">
              <h2 className="text-lg font-bold text-shogun-text">Maintenance &amp; Privacy</h2>
              <p className="text-xs leading-relaxed text-shogun-subdued">
                OpenClaw College ecosystem intelligence is disabled by default. No event is queued or sent until a local administrator explicitly opts in. When enabled, the destination is https://www.openclawcollege.com/api/v1/intelligence/events; HTTPS delivery necessarily exposes network connection metadata.
              </p>
              <p className="text-xs leading-relaxed text-shogun-subdued">
                The security and incident-reporting acknowledgement is separate and is never sent. The sender does not assert or control the recipient&apos;s retention; configured model, provider, and task identifiers are sent as text and truncated to 120, 80, and 80 characters; token, latency, and cost values are bucketed; do not enable College sharing if a configured model, provider, or task identifier contains sensitive information.
              </p>
              <p className="text-xs leading-relaxed text-shogun-subdued">
                Operational exports and evidence aids do not determine legal applicability or compliance. Audit and deletion records are not a guaranteed complete deletion history.
              </p>
            </section>

            <section id="ref-roles-responsibilities" className="shogun-card space-y-3">
              <h2 className="text-lg font-bold text-shogun-text">Roles &amp; Responsibilities</h2>
              <p className="text-xs leading-relaxed text-shogun-subdued">
                Shogun is an orchestration framework—not an AI model. It does not bundle, train, or supply a proprietary LLM or foundation model and is not itself an LLM, foundation model, or general-purpose AI (GPAI) model. It is model-agnostic. Models may be cloud-hosted by third parties or hosted locally by the organisation.
              </p>
              <h3 className="text-sm font-bold text-shogun-text">Alpha Horizon responsibilities</h3>
              <p className="text-xs leading-relaxed text-shogun-subdued">Maintain the official unmodified software, publish security information, and address applicable product obligations.</p>
              <h3 className="text-sm font-bold text-shogun-text">Deploying organisation responsibilities</h3>
              <p className="text-xs leading-relaxed text-shogun-subdued">Select models and providers, configure access, establish lawful use, provide human oversight, validate output, and operate infrastructure.</p>
              <h3 className="text-sm font-bold text-shogun-text">Third-party model and service providers</h3>
              <p className="text-xs leading-relaxed text-shogun-subdued">Those providers remain responsible for their own services, terms, security, and regulatory duties.</p>
              <p className="text-xs leading-relaxed text-shogun-subdued">
                Regulatory roles follow the facts. Use of Shogun does not by itself determine the parties&apos; roles under the EU AI Act. Alpha Horizon may have obligations as a provider or downstream provider in a particular supply chain. Each party must assess and fulfil the duties attached to its actual role. See https://eur-lex.europa.eu/eli/reg/2024/1689/oj. Nothing in this documentation excludes statutory rights or responsibilities.
              </p>
            </section>

            <section id="ref-modified-installations" className="shogun-card space-y-3">
              <h2 className="text-lg font-bold text-shogun-text">Modified Shogun Installations</h2>
              <p className="text-xs leading-relaxed text-shogun-subdued">
                Internal modification is permitted only within the boundaries of the licence. Shogun is source-available—not open source. Restrictions covering sale, resale, rebranding, hosted or managed-service use, and public redistribution remain unchanged. Alpha Horizon does not test, validate, certify, or warrant third-party modifications.
              </p>
              <p className="text-xs leading-relaxed text-shogun-subdued">
                The licence cannot legally exclude rights or duties that applicable law makes non-waivable and does not override any statutory rights. Review https://github.com/AlphaHorizon-AI/Shogun/blob/main/LICENSE.md before modifying or distributing software.
              </p>
            </section>

            <section id="ref-incident-reporting" className="shogun-card space-y-4">
              <h2 className="text-lg font-bold text-shogun-text">Incident Reporting</h2>
              <p className="text-xs leading-relaxed text-shogun-subdued">
                Do <strong>not</strong> publish exploit code, credentials, personal data, or other sensitive details in a public issue. Opening a GitHub report notifies Alpha Horizon but does not itself create a private channel.
              </p>
              <div className="grid gap-3 md:grid-cols-2">
                <a href="https://github.com/AlphaHorizon-AI/Shogun/issues/new" target="_blank" rel="noopener noreferrer" className="rounded-lg border border-shogun-border p-3 text-xs text-shogun-blue">Public, non-sensitive reports</a>
                <a href="https://github.com/AlphaHorizon-AI/Shogun/security/advisories/new" target="_blank" rel="noopener noreferrer" className="rounded-lg border border-shogun-border p-3 text-xs text-shogun-blue">Private security advisory</a>
              </div>
              <a href="mailto:contact@alphahorizon.io?subject=Shogun%20Security%20Report" rel="noopener noreferrer" className="text-xs text-shogun-blue">contact@alphahorizon.io</a>
              <p className="text-xs leading-relaxed text-shogun-subdued">
                The operational targets are acknowledgement within 24 hours, an initial assessment within 72 hours, a remediation decision within 14 days, and coordinated disclosure normally within one month when appropriate. These are handling targets, not a customer-support SLA.
              </p>
              <p className="text-xs leading-relaxed text-shogun-subdued">
                Security-vulnerability handling covers the official unmodified product where required by applicable law. It is not general technical support or a helpdesk for compatibility, feature, integration, modified build, or customer or third-party modification questions. A service-level agreement requires a separate written agreement. The process does not promise a patch for every report.
              </p>
            </section>
          </div>
        )}

        {activeTab === 'architecture' && (
          <div className="space-y-6">
            <section className="shogun-card space-y-3">
              <h2 className="text-lg font-bold text-shogun-text">Governance boundaries</h2>
              <p className="text-xs leading-relaxed text-shogun-subdued">SHRINE is the most restrictive built-in policy for governed agent operations. SHRINE is not a host or container network firewall and should be used together with host-level containment.</p>
              <p className="text-xs leading-relaxed text-shogun-subdued">RONIN is the highest-autonomy built-in tier, not a removal of safety controls; credential entry and administrative escalation remain blocked. Office send, macros, and external Office actions retain approval gates. Human approval: High-risk gates.</p>
              <p className="text-xs leading-relaxed text-shogun-subdued">Ronin desktop control must be enabled separately, and only the RONIN tier permits an operator to enable it. An unknown process defaults to RESTRICTED. The Komainu control is a software input listener; raw coordinates cannot prove the semantic effect of a click, and registry coverage and foreground detection must still be verified.</p>
            </section>
            <section className="shogun-card space-y-3">
              <h2 className="text-lg font-bold text-shogun-text">Execution and evidence limits</h2>
              <p className="text-xs leading-relaxed text-shogun-subdued">Protected files are governed by configured rules. An in-memory content restore point may resume from its last valid checkpoint, but operators must verify external side effects.</p>
              <p className="text-xs leading-relaxed text-shogun-subdued">Configured server-side policy and tool gates reduce risk; they are not a guarantee that prompt injection or every unsafe path is prevented. Environment variables, legacy configuration, plugins, and deployment settings require separate review.</p>
              <p className="text-xs leading-relaxed text-shogun-subdued">Covered operations routed through the Kaizen constitutional validator receive its checks. Custom plugins, integrations, and future execution paths require separate coverage verification.</p>
              <p className="text-xs leading-relaxed text-shogun-subdued">A2A peers can use per-peer shared-secret HMAC, but operators must verify signing and peer authentication separately for every connector. This is not a network-isolation guarantee.</p>
              <p className="text-xs leading-relaxed text-shogun-subdued">In the guarded default, low- and medium-risk calls are allowed by the risk default. In RONIN, the risk default allows low-, medium-, and high-risk calls and blocks critical calls. ToolGate covers registered and instrumented native-tool paths. Custom plugins and uninstrumented execution paths require separate coverage verification.</p>
              <p className="text-xs leading-relaxed text-shogun-subdued">Event correlation supports partial workflow reconstruction; missing events or a missing trace are not proof that an action did or did not occur. Common-mode failures, configuration errors, uninstrumented paths, and compromised infrastructure can cross multiple controls.</p>
            </section>
          </div>
        )}

        {activeTab === 'safety' && (
          <section className="shogun-card space-y-3 border-orange-500/20 bg-orange-500/5">
            <div className="flex items-start gap-3">
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-orange-400" />
              <div className="space-y-3">
                <h2 className="text-lg font-bold text-shogun-text">Emergency controls and operator responsibility</h2>
                <p className="text-xs leading-relaxed text-shogun-subdued">HARAKIRI blocks new governed operations and requests best-effort cancellation of supported active work. It is not a guarantee that every external process stops immediately. The keyboard trigger operates only while the Komainu listener is running and receiving keyboard events. Ronin/Komainu is unavailable in Server mode.</p>
                <p className="text-xs leading-relaxed text-shogun-subdued">Shogun can produce inaccurate or inappropriate output. The deploying organisation remains responsible for its models, providers, data, permissions, infrastructure, use cases, human oversight, and output validation.</p>
              </div>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
