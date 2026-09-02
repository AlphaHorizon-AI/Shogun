export interface SupermodeLayoutAgent {
  id: string;
}

export interface SupermodeLayoutTask {
  id: string;
  assigned_agent_id?: string | null;
}

export interface GraphPosition {
  x: number;
  y: number;
}

export interface SupermodeGraphLayout {
  agentPositions: Map<string, GraphPosition>;
  taskPositions: Map<string, GraphPosition>;
}

export const SUPERMODE_GRAPH_DIMENSIONS = {
  agentColumns: 4,
  agentStartX: 35,
  agentStartY: 180,
  agentColumnStep: 255,
  agentRowMinimumStep: 190,
  taskXOffset: 12,
  taskYOffset: 112,
  taskRowStep: 92,
  unassignedTaskColumnStep: 250,
  unassignedTaskRowStep: 110,
} as const;

/**
 * Lay out each agent with its assigned tasks as one variable-height column.
 * Agent rows grow to contain the busiest column before the next row begins.
 */
export function layoutSupermodeGraph(
  agents: SupermodeLayoutAgent[],
  tasks: SupermodeLayoutTask[],
  showAgents: boolean,
): SupermodeGraphLayout {
  const dimensions = SUPERMODE_GRAPH_DIMENSIONS;
  const visibleAgents = showAgents ? agents : [];
  const visibleAgentIds = new Set(visibleAgents.map(agent => agent.id));
  const assignedTaskCounts = new Map<string, number>();

  for (const task of tasks) {
    const agentId = task.assigned_agent_id;
    if (agentId && visibleAgentIds.has(agentId)) {
      assignedTaskCounts.set(agentId, (assignedTaskCounts.get(agentId) || 0) + 1);
    }
  }

  const agentPositions = new Map<string, GraphPosition>();
  let rowY = dimensions.agentStartY;
  for (let rowStart = 0; rowStart < visibleAgents.length; rowStart += dimensions.agentColumns) {
    const rowAgents = visibleAgents.slice(rowStart, rowStart + dimensions.agentColumns);
    let busiestTaskCount = 0;

    rowAgents.forEach((agent, column) => {
      agentPositions.set(agent.id, {
        x: dimensions.agentStartX + column * dimensions.agentColumnStep,
        y: rowY,
      });
      busiestTaskCount = Math.max(busiestTaskCount, assignedTaskCounts.get(agent.id) || 0);
    });

    rowY += Math.max(
      dimensions.agentRowMinimumStep,
      dimensions.taskYOffset + busiestTaskCount * dimensions.taskRowStep,
    );
  }

  const taskPositions = new Map<string, GraphPosition>();
  const nextTaskIndexByAgent = new Map<string, number>();
  let unassignedTaskIndex = 0;

  for (const task of tasks) {
    const agentId = task.assigned_agent_id;
    const agentPosition = agentId ? agentPositions.get(agentId) : undefined;
    if (agentId && agentPosition) {
      const agentTaskIndex = nextTaskIndexByAgent.get(agentId) || 0;
      nextTaskIndexByAgent.set(agentId, agentTaskIndex + 1);
      taskPositions.set(task.id, {
        x: agentPosition.x + dimensions.taskXOffset,
        y: agentPosition.y + dimensions.taskYOffset + agentTaskIndex * dimensions.taskRowStep,
      });
      continue;
    }

    taskPositions.set(task.id, {
      x: dimensions.agentStartX
        + (unassignedTaskIndex % dimensions.agentColumns) * dimensions.unassignedTaskColumnStep,
      y: rowY
        + Math.floor(unassignedTaskIndex / dimensions.agentColumns) * dimensions.unassignedTaskRowStep,
    });
    unassignedTaskIndex += 1;
  }

  return { agentPositions, taskPositions };
}
