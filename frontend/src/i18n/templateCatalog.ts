import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from './index';

type TemplateCopy = {
  name: string;
  description: string;
};

type StackTemplateCopy = TemplateCopy & {
  duration_label: string;
  builder_labels: Record<string, string>;
};

type TemplateCatalog = {
  ui: Record<string, string>;
  categories: Record<string, string>;
  difficulty: Record<string, string>;
  agentFlow: Record<string, TemplateCopy>;
  flowStack: Record<string, StackTemplateCopy>;
};

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

const catalogModules = import.meta.glob('./templates/*.json', {
  import: 'default',
}) as Record<string, () => Promise<TemplateCatalog>>;
const myTemplatesLabels: Record<string, string> = {
  da: 'Mine skabeloner',
  de: 'Meine Vorlagen',
  es: 'Mis plantillas',
  fr: 'Mes modèles',
  it: 'I miei modelli',
  ja: 'マイテンプレート',
  ko: '내 템플릿',
  no: 'Mine maler',
  pl: 'Moje szablony',
  pt: 'Meus modelos',
  sv: 'Mina mallar',
  uk: 'Мої шаблони',
  zh: '我的模板',
};

export function useTemplateCatalog() {
  const { language } = useTranslation();
  const [catalog, setCatalog] = useState<TemplateCatalog | null>(null);

  useEffect(() => {
    let active = true;
    const load = catalogModules[`./templates/${language}.json`] || catalogModules['./templates/en.json'];
    load?.()
      .then((next) => { if (active) setCatalog(next); })
      .catch(() => catalogModules['./templates/en.json']?.().then((next) => { if (active) setCatalog(next); }));
    return () => { active = false; };
  }, [language]);

  const ui = useCallback(
    (key: string, fallback: string) => catalog?.ui?.[key] || fallback,
    [catalog],
  );

  const category = useCallback(
    (value: string, isCustom = false) => {
      if (isCustom) return value === 'My Templates' ? (myTemplatesLabels[language] || value) : value;
      return catalog?.categories?.[value] || value;
    },
    [catalog, language],
  );

  const difficulty = useCallback(
    (value: string) => catalog?.difficulty?.[value] || value,
    [catalog],
  );

  const agentFlow = useCallback(<T extends CatalogItem>(item: T): T => {
    const isCustom = item.source === 'custom' || item.id.startsWith('custom:');
    const localized = isCustom ? undefined : catalog?.agentFlow?.[item.id];
    return {
      ...item,
      name: localized?.name || item.name,
      description: localized?.description || item.description,
      category: category(item.category, isCustom),
    };
  }, [catalog, category]);

  const flowStack = useCallback(<T extends StackCatalogItem>(item: T): T => {
    const isCustom = item.source === 'custom' || item.id.startsWith('custom:');
    const localized = isCustom ? undefined : catalog?.flowStack?.[item.id];
    return {
      ...item,
      name: localized?.name || item.name,
      description: localized?.description || item.description,
      category: category(item.category, isCustom),
      duration_label: localized?.duration_label || item.duration_label,
      builder_nodes: item.builder_nodes?.map((node) => ({
        ...node,
        label: localized?.builder_labels?.[node.id] || node.label,
      })),
    };
  }, [catalog, category]);

  return { ui, category, difficulty, agentFlow, flowStack };
}
