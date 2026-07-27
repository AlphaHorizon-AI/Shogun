import { describe, expect, it } from 'vitest';

import { setSafeObjectPath } from './safeObjectPath';

describe('setSafeObjectPath', () => {
  it('updates an existing nested property without mutating the source', () => {
    const source = { comms: { enabled: false } };
    expect(setSafeObjectPath(source, 'comms.enabled', true)).toEqual({ comms: { enabled: true } });
    expect(source.comms.enabled).toBe(false);
  });

  it.each(['__proto__.polluted', 'constructor.prototype.polluted', 'missing.value'])(
    'rejects unsafe path %s',
    (path: string) => {
      expect(() => setSafeObjectPath({ comms: { enabled: false } }, path, true)).toThrow();
      expect(({} as Record<string, unknown>).polluted).toBeUndefined();
    },
  );
});
