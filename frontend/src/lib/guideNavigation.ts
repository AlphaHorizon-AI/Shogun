export type GuideTab = 'onboarding' | 'architecture' | 'reference' | 'safety';

const GUIDE_TABS: readonly GuideTab[] = ['onboarding', 'architecture', 'reference', 'safety'];

export function requestedGuideTab(search: string): GuideTab | null {
  const requested = new URLSearchParams(search).get('tab');
  return GUIDE_TABS.includes(requested as GuideTab) ? requested as GuideTab : null;
}

export function requestedGuideSection(
  hash: string,
  knownSectionIds: readonly string[],
): string | null {
  if (!hash.startsWith('#') || hash.length === 1) return null;
  try {
    const requested = decodeURIComponent(hash.slice(1));
    return knownSectionIds.includes(requested) ? requested : null;
  } catch {
    return null;
  }
}
