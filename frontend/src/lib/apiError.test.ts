import { describe, expect, it } from 'vitest';

import { apiDetailMessage, apiErrorMessage } from './apiError';

describe('api error formatting', () => {
  it('renders FastAPI validation details instead of object coercion', () => {
    const error = {
      response: {
        data: {
          detail: [
            {
              loc: ['body', 'nodes', 6, 'config'],
              msg: 'contract execution uses its resolved profile; mappings must be empty',
              type: 'value_error',
            },
          ],
        },
      },
    };

    expect(apiErrorMessage(error, 'Could not save.')).toBe(
      'nodes.6.config: contract execution uses its resolved profile; mappings must be empty'
    );
  });

  it('handles nested and plain API messages', () => {
    expect(apiDetailMessage({ detail: { message: 'Profile not active' } })).toBe(
      'Profile not active'
    );
    expect(apiErrorMessage(new Error('Network unavailable'), 'Fallback')).toBe(
      'Network unavailable'
    );
  });
});
