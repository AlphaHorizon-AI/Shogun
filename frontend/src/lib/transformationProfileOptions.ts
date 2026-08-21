export type TransformationProfileExecutionMode = 'contract' | 'profile';

export type TransformationProfileSourceRequirement = {
  input_kinds: string[];
  transport: string | null;
  object: string | null;
  record_shape: string | null;
  record_path: string | null;
};

export type TransformationProfileOption = {
  profile_id: string;
  display_name: string;
  description?: string | null;
  platform?: string | null;
  domain?: string | null;
  lifecycle?: string | null;
  active_version?: number | null;
  adapter_id?: string | null;
  adapter_status?: string | null;
  required_adapter_status?: string | null;
  selectable: boolean;
  execution_mode: TransformationProfileExecutionMode | null;
  blockers: string[];
  source_requirement: TransformationProfileSourceRequirement;
};

export const isSelectableTransformationProfile = (profile: TransformationProfileOption): boolean =>
  profile.selectable === true && (profile.execution_mode === 'contract' || profile.execution_mode === 'profile');

export const configureNodeForTransformationProfile = (
  currentConfig: Record<string, unknown>,
  option: TransformationProfileOption,
  profileReference: Record<string, unknown>,
): Record<string, unknown> => {
  if (!isSelectableTransformationProfile(option) || !option.execution_mode) {
    throw new Error('Transformation profile is not selectable.');
  }
  const currentOutput = currentConfig.output && typeof currentConfig.output === 'object' && !Array.isArray(currentConfig.output)
    ? currentConfig.output as Record<string, unknown>
    : {};
  const output = option.execution_mode === 'profile' && !['table', 'range'].includes(String(currentOutput.type || 'table'))
    ? {
        ...currentOutput,
        type: 'table',
        start_cell: typeof currentOutput.start_cell === 'string' && /^[A-Za-z]{1,3}[1-9][0-9]*$/.test(currentOutput.start_cell)
          ? currentOutput.start_cell.toUpperCase()
          : 'A1',
      }
    : currentOutput;
  return {
    ...currentConfig,
    execution_mode: option.execution_mode,
    mappings: [],
    input_path: null,
    output,
    transformation_profile: profileReference,
  };
};

export const transformationProfileOptionStatus = (profile: TransformationProfileOption): string => {
  if (isSelectableTransformationProfile(profile)) return 'ready';
  const blockers = Array.isArray(profile.blockers)
    ? profile.blockers.map((blocker) => String(blocker).trim()).filter(Boolean)
    : [];
  if (blockers.length > 0) return blockers.join(' · ');
  return 'not executable';
};

export const transformationProfileSourceLabel = (
  requirement: TransformationProfileSourceRequirement | null | undefined,
): string | null => {
  if (!requirement) return null;
  const parts: string[] = [];
  if (requirement.transport) parts.push(requirement.transport);
  if (requirement.object) parts.push(requirement.object);
  if (requirement.record_shape) parts.push(requirement.record_shape);
  if (requirement.record_path) parts.push(`path ${requirement.record_path}`);
  if (parts.length === 0 && Array.isArray(requirement.input_kinds) && requirement.input_kinds.length > 0) {
    parts.push(requirement.input_kinds.join(' / '));
  }
  return parts.length > 0 ? parts.join(' · ') : null;
};
