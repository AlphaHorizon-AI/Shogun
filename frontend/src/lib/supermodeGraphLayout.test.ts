import { describe, expect, it } from 'vitest';
import {
  layoutSupermodeGraph,
  type GraphPosition,
  type SupermodeLayoutAgent,
  type SupermodeLayoutTask,
} from './supermodeGraphLayout';

type Rectangle = GraphPosition & { id: string; width: number; height: number };

function expectNoOverlaps(rectangles: Rectangle[]) {
  for (let leftIndex = 0; leftIndex < rectangles.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < rectangles.length; rightIndex += 1) {
      const left = rectangles[leftIndex];
      const right = rectangles[rightIndex];
      const separated = left.x + left.width <= right.x
        || right.x + right.width <= left.x
        || left.y + left.height <= right.y
        || right.y + right.height <= left.y;
      expect(separated, `${left.id} overlaps ${right.id}`).toBe(true);
    }
  }
}

describe('layoutSupermodeGraph', () => {
  it('stacks every task beneath its agent and expands later agent rows', () => {
    const agents: SupermodeLayoutAgent[] = Array.from({ length: 6 }, (_, index) => ({
      id: `agent-${index + 1}`,
    }));
    const tasks: SupermodeLayoutTask[] = [
      { id: 'task-1a', assigned_agent_id: 'agent-1' },
      { id: 'task-1b', assigned_agent_id: 'agent-1' },
      { id: 'task-1c', assigned_agent_id: 'agent-1' },
      { id: 'task-2a', assigned_agent_id: 'agent-2' },
      { id: 'task-2b', assigned_agent_id: 'agent-2' },
      { id: 'task-4a', assigned_agent_id: 'agent-4' },
      { id: 'task-5a', assigned_agent_id: 'agent-5' },
    ];

    const layout = layoutSupermodeGraph(agents, tasks, true);
    const rectangles: Rectangle[] = [
      ...agents.map(agent => ({
        id: agent.id,
        ...layout.agentPositions.get(agent.id)!,
        width: 210,
        height: 74,
      })),
      ...tasks.map(task => ({
        id: task.id,
        ...layout.taskPositions.get(task.id)!,
        width: 190,
        height: 62,
      })),
    ];

    expect(layout.taskPositions.get('task-1b')!.y).toBeGreaterThan(
      layout.taskPositions.get('task-1a')!.y,
    );
    expect(layout.agentPositions.get('agent-5')!.y).toBeGreaterThan(
      layout.taskPositions.get('task-1c')!.y + 62,
    );
    expectNoOverlaps(rectangles);
  });

  it('places unassigned tasks after all agent task columns', () => {
    const agents = [{ id: 'agent-1' }];
    const tasks = [
      { id: 'assigned-1', assigned_agent_id: 'agent-1' },
      { id: 'assigned-2', assigned_agent_id: 'agent-1' },
      { id: 'unassigned' },
    ];

    const layout = layoutSupermodeGraph(agents, tasks, true);

    expect(layout.taskPositions.get('unassigned')!.y).toBeGreaterThan(
      layout.taskPositions.get('assigned-2')!.y + 62,
    );
  });

  it('uses a non-overlapping task grid when agent cards are hidden', () => {
    const tasks = Array.from({ length: 9 }, (_, index) => ({
      id: `task-${index + 1}`,
      assigned_agent_id: 'hidden-agent',
    }));
    const layout = layoutSupermodeGraph([{ id: 'hidden-agent' }], tasks, false);

    expect(layout.agentPositions.size).toBe(0);
    expectNoOverlaps(tasks.map(task => ({
      id: task.id,
      ...layout.taskPositions.get(task.id)!,
      width: 190,
      height: 62,
    })));
  });
});
