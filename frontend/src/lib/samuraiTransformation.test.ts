import { describe, expect, it } from 'vitest';

import {
  appendSamuraiAutoCandidate,
  configureSamuraiForPrivateProfile,
  configureSamuraiForRegistryProfile,
  configureSamuraiTransformationChoice,
  isSamuraiContractProfile,
  removeSamuraiAutoCandidate,
  samuraiTransformationBadge,
  samuraiTransformationChoice,
  samuraiTransformationConfigurationError,
} from './samuraiTransformation';
import type { TransformationProfileOption } from './transformationProfileOptions';

const contractOption = (patch: Partial<TransformationProfileOption> = {}): TransformationProfileOption => ({
  profile_id: 'document_contract_v2',
  display_name: 'Document contract',
  lifecycle: 'active',
  active_version: 2,
  adapter_id: 'sectioned_record_matrix_v1',
  adapter_status: 'available',
  required_adapter_status: 'available',
  selectable: true,
  execution_mode: 'contract',
  blockers: [],
  source_requirement: {
    input_kinds: ['pdf'],
    transport: 'PDF',
    object: 'planning report',
    record_shape: 'sectioned records',
    record_path: null,
  },
  ...patch,
});

const registryReference = {
  id: 'document_contract_v2',
  adapter: 'sectioned_record_matrix_v1',
  parameters: {},
  model_fallback: false,
  registry_version: 2,
  content_hash: 'a'.repeat(64),
};

describe('Samurai transformation configuration', () => {
  it('keeps existing Samurai nodes on general LLM by default', () => {
    expect(samuraiTransformationChoice({ task_description: 'Summarize this.' })).toBe('general');
    expect(samuraiTransformationBadge({ task_description: 'Summarize this.' })).toBe('General LLM');
  });

  it('removes an incompatible profile when switching modes', () => {
    const configured = configureSamuraiTransformationChoice({
      transformation_mode: 'profile',
      transformation_profile: registryReference,
    }, 'auto');
    expect(configured).toEqual({ transformation_mode: 'auto' });
  });

  it('distinguishes pinned catalogue and imported private profiles', () => {
    expect(samuraiTransformationChoice({
      transformation_mode: 'profile',
      transformation_profile: registryReference,
    })).toBe('catalogue');
    expect(samuraiTransformationChoice({
      transformation_mode: 'profile',
      transformation_profile: {
        id: 'tenant-private-v1',
        adapter: 'sectioned_record_matrix_v1',
        private_file: { content_hash: 'b'.repeat(64) },
      },
    })).toBe('private');
  });

  it('allows only ready contract-mode catalogue profiles', () => {
    expect(isSamuraiContractProfile(contractOption())).toBe(true);
    expect(isSamuraiContractProfile(contractOption({ execution_mode: 'profile' }))).toBe(false);
    expect(() => configureSamuraiForRegistryProfile(
      {},
      contractOption({ execution_mode: 'profile' }),
      registryReference,
    )).toThrow('Only ready document-contract profiles');
  });

  it('pins a registry contract without changing unrelated Samurai settings', () => {
    expect(configureSamuraiForRegistryProfile(
      { task_description: 'Extract records.' },
      contractOption(),
      registryReference,
    )).toEqual({
      task_description: 'Extract records.',
      transformation_mode: 'profile',
      transformation_profile: registryReference,
    });
  });

  it('accepts an integrity-referenced private profile and rejects a registry-shaped one', () => {
    const privateReference = {
      id: 'tenant-private-v1',
      adapter: 'sectioned_record_matrix_v1',
      model_fallback: false,
      private_file: { content_hash: 'b'.repeat(64), filename: 'tenant.shogun-profile.json' },
    };
    expect(configureSamuraiForPrivateProfile({}, privateReference)).toEqual({
      transformation_mode: 'profile',
      transformation_profile: privateReference,
    });
    expect(() => configureSamuraiForPrivateProfile({}, registryReference)).toThrow(
      'valid private profile reference',
    );
  });

  it('validates fail-closed serialized mode and profile combinations', () => {
    expect(samuraiTransformationConfigurationError({})).toBeNull();
    expect(samuraiTransformationConfigurationError({ transformation_mode: 'auto' })).toBeNull();
    expect(samuraiTransformationConfigurationError({
      transformation_mode: 'auto',
      transformation_profile: registryReference,
    })).toContain('cannot also carry');
    expect(samuraiTransformationConfigurationError({
      transformation_mode: 'profile',
      transformation_profile: registryReference,
    })).toBeNull();
    expect(samuraiTransformationConfigurationError({ transformation_mode: 'profile' })).toContain(
      'select a governed document contract',
    );
  });

  it('adds, deduplicates, and removes private auto-detect candidates', () => {
    const privateReference = {
      id: 'tenant-private-v1',
      adapter: 'sectioned_record_matrix_v1',
      model_fallback: false,
      private_file: { content_hash: 'b'.repeat(64), definition: { id: 'tenant-private-v1' } },
    };
    const configured = appendSamuraiAutoCandidate({ transformation_mode: 'auto' }, privateReference);
    expect(configured.transformation_candidates).toEqual([privateReference]);
    expect(samuraiTransformationBadge(configured)).toBe('Auto-detect · 1 private');
    expect(appendSamuraiAutoCandidate(configured, privateReference).transformation_candidates).toEqual([privateReference]);
    expect(removeSamuraiAutoCandidate(configured, 0)).toEqual({ transformation_mode: 'auto' });
  });

  it('preserves the executable private definition without exposing it in the badge', () => {
    const privateReference = {
      id: 'tenant-private-v1',
      adapter: 'sectioned_record_matrix_v1',
      private_file: {
        content_hash: 'c'.repeat(64),
        definition: { parameters: { proprietary_marker: 'never-render-this-value' } },
      },
    };
    const configured = appendSamuraiAutoCandidate({ transformation_mode: 'auto' }, privateReference);
    expect(configured.transformation_candidates).toEqual([privateReference]);
    expect(samuraiTransformationBadge(configured)).toBe('Auto-detect · 1 private');
    expect(samuraiTransformationBadge(configured)).not.toContain('never-render-this-value');
  });

  it('clears private candidates when leaving auto-detect', () => {
    const autoConfig = {
      transformation_mode: 'auto',
      transformation_candidates: [{ private_file: { content_hash: 'b'.repeat(64) } }],
    };
    expect(configureSamuraiTransformationChoice(autoConfig, 'general')).toEqual({
      transformation_mode: 'general',
    });
    expect(configureSamuraiTransformationChoice(autoConfig, 'catalogue')).toEqual({
      transformation_mode: 'profile',
    });
  });
});
