import { describe, expect, it } from 'vitest';

import {
  configureNodeForTransformationProfile,
  isSelectableTransformationProfile,
  transformationProfileOptionStatus,
  transformationProfileSourceLabel,
  type TransformationProfileOption,
} from './transformationProfileOptions';

const option = (patch: Partial<TransformationProfileOption> = {}): TransformationProfileOption => ({
  profile_id: 'synthetic_orders_v1',
  display_name: 'Synthetic orders',
  lifecycle: 'active',
  active_version: 2,
  adapter_id: 'canonical_entity_map_v1',
  adapter_status: 'available',
  required_adapter_status: 'available',
  selectable: true,
  execution_mode: 'profile',
  blockers: [],
  source_requirement: {
    input_kinds: ['json_object', 'json_array'],
    transport: 'REST',
    object: 'orders',
    record_shape: 'collection',
    record_path: 'value',
  },
  ...patch,
});

describe('transformation profile API options', () => {
  it('uses the backend selectable decision as authoritative', () => {
    expect(isSelectableTransformationProfile(option())).toBe(true);
    expect(isSelectableTransformationProfile(option({
      selectable: false,
      blockers: ['active version is missing'],
    }))).toBe(false);
  });

  it('does not enable an option without a supported execution mode', () => {
    const unsupported = option({
      selectable: true,
      execution_mode: null,
      blockers: ['adapter has no AgentFlow execution mode'],
    });
    expect(isSelectableTransformationProfile(unsupported)).toBe(false);
    expect(transformationProfileOptionStatus(unsupported)).toBe(
      'adapter has no AgentFlow execution mode',
    );
  });

  it('configures an enterprise selection as profile mode and removes visual mappings', () => {
    const configured = configureNodeForTransformationProfile(
      {
        execution_mode: 'transform',
        input_path: 'legacy.items',
        mappings: [{ source: 'id', target: 'A' }],
        output: { type: 'cells', start_cell: 'b4', sheet: 'Import' },
      },
      option(),
      { id: 'synthetic_orders_v1', adapter: 'canonical_entity_map_v1' },
    );
    expect(configured.execution_mode).toBe('profile');
    expect(configured.mappings).toEqual([]);
    expect(configured.input_path).toBeNull();
    expect(configured.output).toEqual({ type: 'table', start_cell: 'B4', sheet: 'Import' });
    expect(configured.transformation_profile).toEqual({
      id: 'synthetic_orders_v1',
      adapter: 'canonical_entity_map_v1',
    });
  });

  it('formats the structured source requirement without guessing', () => {
    expect(transformationProfileSourceLabel(option().source_requirement)).toBe(
      'REST · orders · collection · path value',
    );
  });
});
