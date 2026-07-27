const FORBIDDEN_PATH_SEGMENTS = new Set(['__proto__', 'prototype', 'constructor']);

/** Clone an object and update an existing nested property without prototype access. */
export function setSafeObjectPath<T extends object>(source: T, path: string, value: unknown): T {
  const keys = path.split('.');
  if (!keys.length || keys.some((key) => !key || FORBIDDEN_PATH_SEGMENTS.has(key))) {
    throw new Error('Unsafe configuration path');
  }

  const updated = structuredClone(source);
  let current: Record<string, unknown> = updated as Record<string, unknown>;
  for (const key of keys.slice(0, -1)) {
    if (!Object.prototype.hasOwnProperty.call(current, key)) {
      throw new Error('Unknown configuration path');
    }
    const next = current[key];
    if (next === null || typeof next !== 'object' || Array.isArray(next)) {
      throw new Error('Invalid configuration path');
    }
    current = next as Record<string, unknown>;
  }
  const finalKey = keys.at(-1)!;
  if (!Object.prototype.hasOwnProperty.call(current, finalKey)) {
    throw new Error('Unknown configuration property');
  }
  current[finalKey] = value;
  return updated;
}
