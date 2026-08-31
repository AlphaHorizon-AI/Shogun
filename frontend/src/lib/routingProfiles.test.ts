import { describe, expect, it } from 'vitest';

import {
  customProfileUpdate,
  resolveAgentRoutingProfile,
  routingProfileLabel,
} from './routingProfiles';

describe('routing profiles', () => {
  it('uses the canonical selected profile instead of stale inline agent data', () => {
    const selected = { id: 'named-id', name: 'Finance Research', is_default: true };

    expect(resolveAgentRoutingProfile({
      model_routing_profile_id: 'named-id',
      routing_profile: { id: 'old-id', name: 'Custom' },
    }, [selected])).toEqual(selected);
    expect(routingProfileLabel(selected)).toBe('Finance Research (Default)');
  });

  it('builds a persistent named-profile payload from the generic Custom template', () => {
    expect(customProfileUpdate(
      { id: 'custom-id', name: 'Custom', description: null },
      ['primary', 'fallback-one', 'fallback-two'],
      '  Finance Research  ',
      ' Finance models ',
    )).toEqual({
      name: 'Finance Research',
      description: 'Finance models',
      rules: [{
        task_type: '*',
        primary_model_id: 'primary',
        fallback_model_ids: ['fallback-one', 'fallback-two'],
      }],
    });
  });

  it('updates an existing profile description without renaming it from the new-profile draft', () => {
    expect(customProfileUpdate(
      { id: 'finance-id', name: 'Finance Research' },
      ['primary'],
      'Another profile',
      'Another description',
    )).toEqual({
      description: 'Another description',
      rules: [{
        task_type: '*',
        primary_model_id: 'primary',
        fallback_model_ids: [],
      }],
    });
  });
});
