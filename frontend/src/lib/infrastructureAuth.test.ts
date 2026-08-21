import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  consumeInfrastructureTokenFromLocation,
  getInfrastructureAdminToken,
} from './infrastructureAuth';

function installWindow(hash: string) {
  const values = new Map<string, string>();
  const replaceState = vi.fn();
  vi.stubGlobal('window', {
    location: {
      hash,
      pathname: '/setup',
      search: '?deployment=server',
      origin: 'https://shogun.example.test',
    },
    history: {
      state: { preserved: true },
      replaceState,
    },
    sessionStorage: {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
    },
  });
  return { replaceState, values };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('infrastructure setup token bootstrap', () => {
  it('decodes, stores, and removes a fragment token before setup requests begin', () => {
    const token = `${'a'.repeat(32)}+/?#&=`;
    const { replaceState } = installWindow(
      `#infrastructure_token=${encodeURIComponent(token)}`,
    );

    expect(consumeInfrastructureTokenFromLocation()).toBe(true);
    expect(getInfrastructureAdminToken()).toBe(token);
    expect(replaceState).toHaveBeenCalledOnce();
    expect(replaceState).toHaveBeenCalledWith(
      { preserved: true },
      '',
      '/setup?deployment=server',
    );
    expect(JSON.stringify(replaceState.mock.calls)).not.toContain(token);
  });

  it('does not consume ordinary application anchors', () => {
    const { replaceState } = installWindow('#ref-incident-reporting');

    expect(consumeInfrastructureTokenFromLocation()).toBe(false);
    expect(getInfrastructureAdminToken()).toBe('');
    expect(replaceState).not.toHaveBeenCalled();
  });

  it('removes an empty credential fragment without storing a token', () => {
    const { replaceState } = installWindow('#infrastructure_token=');

    expect(consumeInfrastructureTokenFromLocation()).toBe(false);
    expect(getInfrastructureAdminToken()).toBe('');
    expect(replaceState).toHaveBeenCalledWith(
      { preserved: true },
      '',
      '/setup?deployment=server',
    );
  });
});
