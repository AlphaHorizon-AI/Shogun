import { describe, expect, it } from 'vitest';

import { formatRecordCount } from './formatRecordCount';

describe('formatRecordCount', () => {
  it('preserves a legitimate zero count', () => {
    expect(formatRecordCount(0)).toBe('0');
  });

  it('does not invent a count while the overview value is unavailable', () => {
    expect(formatRecordCount(undefined)).toBe('—');
    expect(formatRecordCount(null)).toBe('—');
  });

  it('formats the live backend count', () => {
    expect(formatRecordCount(1248)).toBe((1248).toLocaleString());
  });
});
