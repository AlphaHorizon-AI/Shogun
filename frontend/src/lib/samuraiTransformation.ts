import {
  isSelectableTransformationProfile,
  type TransformationProfileOption,
} from './transformationProfileOptions';

export type SamuraiTransformationMode = 'general' | 'auto' | 'profile';

export type SamuraiTransformationChoice =
  | 'general'
  | 'auto'
  | 'catalogue'
  | 'private';

type ProfileReference = Record<string, unknown> & {
  id?: unknown;
  adapter?: unknown;
  registry_version?: unknown;
  content_hash?: unknown;
  private_file?: unknown;
};

export const MAX_SAMURAI_PRIVATE_CANDIDATES = 32;

const isObject = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value);

export const samuraiTransformationChoice = (
  config: Record<string, unknown>,
): SamuraiTransformationChoice => {
  if (config.transformation_mode === 'auto') return 'auto';
  if (config.transformation_mode !== 'profile') return 'general';
  const profile = isObject(config.transformation_profile)
    ? config.transformation_profile as ProfileReference
    : null;
  return profile && isObject(profile.private_file) ? 'private' : 'catalogue';
};

export const configureSamuraiTransformationChoice = (
  currentConfig: Record<string, unknown>,
  choice: SamuraiTransformationChoice,
): Record<string, unknown> => {
  const nextConfig = { ...currentConfig };
  const profile = isObject(nextConfig.transformation_profile)
    ? nextConfig.transformation_profile as ProfileReference
    : null;

  if (choice === 'general' || choice === 'auto') {
    nextConfig.transformation_mode = choice;
    delete nextConfig.transformation_profile;
    if (choice === 'general') delete nextConfig.transformation_candidates;
    return nextConfig;
  }

  nextConfig.transformation_mode = 'profile';
  delete nextConfig.transformation_candidates;
  const hasPrivateFile = profile && isObject(profile.private_file);
  if (
    !profile
    || (choice === 'private' && !hasPrivateFile)
    || (choice === 'catalogue' && hasPrivateFile)
  ) {
    delete nextConfig.transformation_profile;
  }
  return nextConfig;
};

export const isSamuraiContractProfile = (
  option: TransformationProfileOption,
): boolean => option.execution_mode === 'contract';

export const configureSamuraiForRegistryProfile = (
  currentConfig: Record<string, unknown>,
  option: TransformationProfileOption,
  profileReference: ProfileReference,
): Record<string, unknown> => {
  if (!isSamuraiContractProfile(option) || !isSelectableTransformationProfile(option)) {
    throw new Error('Only ready document-contract profiles can be pinned to Samurai.');
  }
  if (
    !profileReference.id
    || !profileReference.adapter
    || !Number.isInteger(profileReference.registry_version)
    || typeof profileReference.content_hash !== 'string'
    || !/^[a-fA-F0-9]{64}$/.test(profileReference.content_hash)
    || isObject(profileReference.private_file)
  ) {
    throw new Error('The registry profile reference is not an immutable pin.');
  }
  const nextConfig: Record<string, unknown> = {
    ...currentConfig,
    transformation_mode: 'profile',
    transformation_profile: profileReference,
  };
  delete nextConfig.transformation_candidates;
  return nextConfig;
};

export const configureSamuraiForPrivateProfile = (
  currentConfig: Record<string, unknown>,
  profileReference: ProfileReference,
): Record<string, unknown> => {
  if (
    !profileReference.id
    || !profileReference.adapter
    || !isObject(profileReference.private_file)
    || Number.isInteger(profileReference.registry_version)
  ) {
    throw new Error('The imported file did not provide a valid private profile reference.');
  }
  const nextConfig: Record<string, unknown> = {
    ...currentConfig,
    transformation_mode: 'profile',
    transformation_profile: profileReference,
  };
  delete nextConfig.transformation_candidates;
  return nextConfig;
};

export const appendSamuraiAutoCandidate = (
  currentConfig: Record<string, unknown>,
  profileReference: ProfileReference,
): Record<string, unknown> => {
  if (
    !profileReference.id
    || !profileReference.adapter
    || !isObject(profileReference.private_file)
    || Number.isInteger(profileReference.registry_version)
  ) {
    throw new Error('Auto-detect candidates must be portable private profile references.');
  }
  const privateFile = profileReference.private_file as Record<string, unknown>;
  const contentHash = privateFile.content_hash;
  if (typeof contentHash !== 'string' || !/^[a-fA-F0-9]{64}$/.test(contentHash)) {
    throw new Error('The private candidate is missing its integrity hash.');
  }
  const currentCandidates = Array.isArray(currentConfig.transformation_candidates)
    ? currentConfig.transformation_candidates.filter(isObject) as ProfileReference[]
    : [];
  const duplicateIndex = currentCandidates.findIndex((candidate) => {
    const candidatePrivateFile = isObject(candidate.private_file) ? candidate.private_file : null;
    return candidate.id === profileReference.id
      && candidatePrivateFile?.content_hash === contentHash;
  });
  const nextCandidates = duplicateIndex >= 0
    ? currentCandidates.map((candidate, index) => index === duplicateIndex ? profileReference : candidate)
    : [...currentCandidates, profileReference];
  if (nextCandidates.length > MAX_SAMURAI_PRIVATE_CANDIDATES) {
    throw new Error(`Auto-detect accepts at most ${MAX_SAMURAI_PRIVATE_CANDIDATES} private candidates.`);
  }
  const nextConfig: Record<string, unknown> = {
    ...currentConfig,
    transformation_mode: 'auto',
    transformation_candidates: nextCandidates,
  };
  delete nextConfig.transformation_profile;
  return nextConfig;
};

export const removeSamuraiAutoCandidate = (
  currentConfig: Record<string, unknown>,
  candidateIndex: number,
): Record<string, unknown> => {
  const currentCandidates = Array.isArray(currentConfig.transformation_candidates)
    ? currentConfig.transformation_candidates.filter(isObject)
    : [];
  const nextCandidates = currentCandidates.filter((_, index) => index !== candidateIndex);
  const nextConfig = { ...currentConfig };
  if (nextCandidates.length > 0) nextConfig.transformation_candidates = nextCandidates;
  else delete nextConfig.transformation_candidates;
  return nextConfig;
};

export const samuraiTransformationBadge = (config: Record<string, unknown>): string => {
  const choice = samuraiTransformationChoice(config);
  if (choice === 'general') return 'General LLM';
  if (choice === 'auto') {
    const privateCount = Array.isArray(config.transformation_candidates)
      ? config.transformation_candidates.length
      : 0;
    return privateCount > 0
      ? `Auto-detect · ${privateCount} private`
      : 'Auto-detect';
  }
  const profile = isObject(config.transformation_profile)
    ? config.transformation_profile as ProfileReference
    : null;
  const profileId = typeof profile?.id === 'string' && profile.id.trim()
    ? profile.id.trim()
    : 'profile required';
  return choice === 'private' ? `Private · ${profileId}` : `Pinned · ${profileId}`;
};

export const samuraiTransformationConfigurationError = (
  config: Record<string, unknown>,
): string | null => {
  const mode = config.transformation_mode === undefined ? 'general' : config.transformation_mode;
  if (mode !== 'general' && mode !== 'auto' && mode !== 'profile') {
    return 'select a supported transformation mode';
  }
  const profile = isObject(config.transformation_profile)
    ? config.transformation_profile as ProfileReference
    : null;
  if (mode === 'general' || mode === 'auto') {
    if (profile) return `${mode} mode cannot also carry a pinned transformation profile`;
    const candidates = config.transformation_candidates;
    if (mode === 'general' && Array.isArray(candidates) && candidates.length > 0) {
      return 'general mode cannot carry auto-detect private candidates';
    }
    if (mode === 'auto' && candidates !== undefined) {
      if (!Array.isArray(candidates) || candidates.length > MAX_SAMURAI_PRIVATE_CANDIDATES) {
        return `auto-detect accepts at most ${MAX_SAMURAI_PRIVATE_CANDIDATES} private candidates`;
      }
      for (const candidate of candidates) {
        if (!isObject(candidate) || !isObject(candidate.private_file)) {
          return 'auto-detect candidates must be imported private profile files';
        }
      }
    }
    return null;
  }
  if (Array.isArray(config.transformation_candidates) && config.transformation_candidates.length > 0) {
    return 'pinned profile mode cannot also carry auto-detect candidates';
  }
  if (!profile || typeof profile.id !== 'string' || !profile.id.trim()) {
    return 'select a governed document contract or import a private profile file';
  }
  if (typeof profile.adapter !== 'string' || !profile.adapter.trim()) {
    return 'the selected document profile is missing its adapter';
  }
  const hasPrivateFile = isObject(profile.private_file);
  const hasRegistryVersion = Number.isInteger(profile.registry_version);
  const hasRegistryHash = typeof profile.content_hash === 'string'
    && /^[a-fA-F0-9]{64}$/.test(profile.content_hash);
  if (hasPrivateFile && (hasRegistryVersion || profile.content_hash !== undefined)) {
    return 'private and registry profile references cannot be combined';
  }
  if (!hasPrivateFile && (!hasRegistryVersion || !hasRegistryHash)) {
    return 'select the catalogue profile again to create an immutable version and hash pin';
  }
  return null;
};
