import { describe, expect, it } from 'vitest';

import { requestedGuideSection, requestedGuideTab } from './guideNavigation';


describe('Guide deep-link parsing', () => {
  it('opens the reference tab and Incident Reporting section', () => {
    const url = new URL(
      'http://localhost/guide?tab=reference#ref-incident-reporting',
    );

    expect(requestedGuideTab(url.search)).toBe('reference');
    expect(
      requestedGuideSection(url.hash, ['ref-tenshu', 'ref-incident-reporting']),
    ).toBe('ref-incident-reporting');
  });

  it('rejects unsupported tabs, unknown sections, and malformed encoding', () => {
    expect(requestedGuideTab('?tab=admin')).toBeNull();
    expect(requestedGuideSection('#ref-unknown', ['ref-tenshu'])).toBeNull();
    expect(requestedGuideSection('#%E0%A4%A', ['ref-tenshu'])).toBeNull();
  });
});
