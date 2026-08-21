import { describe, expect, it } from 'vitest';

import { parsePrivateProfileDocument, privateProfileFilename } from './privateProfileFile';

describe('private profile files', () => {
  it('creates a safe, recognizable filename', () => {
    expect(privateProfileFilename('Customer / Report: private v2.json')).toBe(
      'Customer-Report-private-v2.shogun-profile.json',
    );
    expect(privateProfileFilename('')).toBe(
      'private-transformation-profile.shogun-profile.json',
    );
  });

  it('accepts exactly one JSON object', () => {
    expect(parsePrivateProfileDocument('{"format":"shogun.private-transformation-profile"}')).toEqual({
      format: 'shogun.private-transformation-profile',
    });
    expect(() => parsePrivateProfileDocument('[]')).toThrow('must contain one JSON object');
    expect(() => parsePrivateProfileDocument('{broken')).toThrow('not valid JSON');
  });
});
