export type RoutingProfileLike = {
  id: string;
  name: string;
  description?: string | null;
  is_default?: boolean;
};

export type AgentRoutingSelection = {
  model_routing_profile_id?: string | null;
  routing_profile?: RoutingProfileLike | null;
};

export const routingProfileLabel = (profile: RoutingProfileLike, defaultLabel = 'Default') =>
  `${profile.name}${profile.is_default ? ` (${defaultLabel})` : ''}`;

export const resolveAgentRoutingProfile = (
  agent: AgentRoutingSelection,
  profiles: RoutingProfileLike[],
): RoutingProfileLike | null => {
  const selectedId = agent.model_routing_profile_id ? String(agent.model_routing_profile_id) : '';
  return profiles.find(profile => String(profile.id) === selectedId)
    || agent.routing_profile
    || null;
};

export const customProfileUpdate = (
  profile: RoutingProfileLike,
  modelIds: string[],
  pendingName: string,
  pendingDescription: string,
) => {
  const name = pendingName.trim();
  const description = pendingDescription.trim();
  const renameGenericProfile = profile.name === 'Custom' && Boolean(name);

  return {
    rules: [{
      task_type: '*',
      primary_model_id: modelIds[0],
      fallback_model_ids: modelIds.slice(1),
    }],
    ...(renameGenericProfile
      ? { name, description: description || profile.description || null }
      : { description: description || null }),
  };
};
