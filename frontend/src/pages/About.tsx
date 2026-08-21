import { useEffect, useState } from 'react';
import {
  Building2,
  CalendarDays,
  ExternalLink,
  GitCommitHorizontal,
  Info,
  Package,
  ShieldCheck,
} from 'lucide-react';

interface ReleaseIdentity {
  product: string;
  version: string;
  build: number;
  release_id: string;
  channel: string;
  release_date: string | null;
  git_sha: string | null;
  git_sha_source: string | null;
  working_tree_modified: boolean | null;
  distribution_status: 'tracked_checkout_clean' | 'locally_modified' | 'release_evidence_present' | 'update_overlay_unverified' | 'unverified';
  developer: string;
  official_repository: string;
  official_repository_url: string;
}

const OFFICIAL_REPOSITORY_URL = 'https://github.com/AlphaHorizon-AI/Shogun';

const displayDate = (value: string | null) => {
  if (!value) return 'Not recorded for this build';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
};

const displayDistributionStatus = (release: ReleaseIdentity | null) => {
  if (!release) return undefined;
  switch (release.distribution_status) {
    case 'tracked_checkout_clean': return 'Tracked checkout matches the base commit';
    case 'locally_modified': return 'Tracked source files are modified locally';
    case 'release_evidence_present': return 'Release evidence present; local modifications not independently verified';
    case 'update_overlay_unverified': return 'Updater source recorded; local modifications not independently verified';
    default: return 'Modification status could not be verified';
  }
};

export const About = () => {
  const [release, setRelease] = useState<ReleaseIdentity | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetch('/api/v1/updates/version', { cache: 'no-store' })
      .then(async response => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then(payload => {
        if (active) setRelease(payload.release || null);
      })
      .catch(() => {
        if (active) setError('Release identity is temporarily unavailable.');
      });
    return () => { active = false; };
  }, []);

  const rows = [
    { label: 'Product', value: release?.product, icon: Package },
    { label: 'Version', value: release?.version ? `v${release.version}` : undefined, icon: Info },
    { label: 'Build / release identifier', value: release?.release_id, icon: ShieldCheck },
    { label: 'Release channel', value: release?.channel, icon: ShieldCheck },
    { label: 'Release date', value: release ? displayDate(release.release_date) : undefined, icon: CalendarDays },
    { label: 'Base / source commit', value: release?.git_sha || (release ? 'Not embedded in this build' : undefined), icon: GitCommitHorizontal, mono: true },
    { label: 'Distribution status', value: displayDistributionStatus(release), icon: ShieldCheck },
    { label: 'Developer', value: release?.developer, icon: Building2 },
  ];

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <Info className="w-6 h-6 text-shogun-gold" />
          About Shogun
        </h1>
        <p className="text-shogun-subdued mt-1">
          Installed product and official release identity. No installation or user identifiers are shown here.
        </p>
      </div>

      {error && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">
          {error}
        </div>
      )}

      <section className="rounded-xl border border-shogun-border bg-shogun-card overflow-hidden">
        <div className="border-b border-shogun-border px-6 py-4">
          <h2 className="font-semibold text-shogun-text">System information</h2>
          <p className="mt-1 text-xs text-shogun-subdued">
            Use this information when checking release notes or preparing a security report.
          </p>
        </div>
        <dl className="divide-y divide-shogun-border/50">
          {rows.map(({ label, value, icon: Icon, mono }) => (
            <div key={label} className="grid gap-2 px-6 py-4 sm:grid-cols-[220px_1fr]">
              <dt className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-shogun-subdued">
                <Icon className="h-4 w-4 text-shogun-blue" />
                {label}
              </dt>
              <dd className={`${mono ? 'font-mono break-all' : ''} text-sm text-shogun-text`}>
                {value || 'Loading…'}
              </dd>
            </div>
          ))}
          <div className="grid gap-2 px-6 py-4 sm:grid-cols-[220px_1fr]">
            <dt className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-shogun-subdued">
              <ExternalLink className="h-4 w-4 text-shogun-blue" />
              Official repository
            </dt>
            <dd className="text-sm">
              <a
                href={OFFICIAL_REPOSITORY_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-shogun-blue hover:underline"
              >
                {release?.official_repository || 'AlphaHorizon-AI/Shogun'}
                <ExternalLink className="h-3 w-3" />
              </a>
            </dd>
          </div>
        </dl>
      </section>

      <p className="text-xs leading-relaxed text-shogun-subdued">
        A commit identifies the recorded base source; it does not by itself prove that installed files are unmodified. Independent
        source-code modifications may change behaviour and are not represented as reviewed or validated by Alpha Horizon merely
        because an official version identifier remains present.
      </p>
    </div>
  );
};
