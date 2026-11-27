import { useCallback } from 'react';

type CatalogItem = {
  id: string;
  name: string;
  description: string;
  category: string;
  difficulty?: string;
  source?: string;
};

type StackCatalogItem = CatalogItem & {
  duration_label?: string;
  builder_nodes?: Array<{ id: string; label: string; [key: string]: unknown }>;
};

export function useTemplateCatalog() {
  const ui = useCallback((_key: string, fallback: string) => fallback, []);
  const category = useCallback((value: string, _isCustom = false) => value, []);
  const difficulty = useCallback((value: string) => value, []);
  const agentFlow = useCallback(<T extends CatalogItem>(item: T): T => item, []);
  const flowStack = useCallback(<T extends StackCatalogItem>(item: T): T => item, []);

  return { ui, category, difficulty, agentFlow, flowStack };
}
