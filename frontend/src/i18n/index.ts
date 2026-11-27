import React, { createContext, useContext } from 'react';
import type { ReactNode } from 'react';
import enPack from './en.json';

type TranslationMap = Record<string, unknown>;

interface I18nContextType {
  language: string;
  setLanguage: (code: string) => Promise<void>;
  t: (key: string, fallback?: string) => string;
  loading: boolean;
}

function resolveKey(translations: TranslationMap, key: string): string | undefined {
  let current: unknown = translations;
  for (const part of key.split('.')) {
    if (current == null || typeof current !== 'object') return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return typeof current === 'string' ? current : undefined;
}

const translate = (key: string, fallback?: string): string => {
  return resolveKey(enPack as TranslationMap, key) || fallback || key.split('.').pop() || key;
};

const I18nContext = createContext<I18nContextType>({
  language: 'en',
  setLanguage: async () => {},
  t: translate,
  loading: false,
});

export const I18nProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  return React.createElement(
    I18nContext.Provider,
    {
      value: {
        language: 'en',
        setLanguage: async () => {},
        t: translate,
        loading: false,
      },
    },
    children,
  );
};

export const useTranslation = (): I18nContextType => useContext(I18nContext);
