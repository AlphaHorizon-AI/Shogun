/**
 * Shogun i18n — Internationalization system.
 *
 * Provides a React context + hook for multi-language support.
 * Language packs are loaded on demand and cached so the initial bundle contains
 * only the language loader rather than every translation catalog.
 */

import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import type { ReactNode } from 'react';

// ── Types ────────────────────────────────────────────────────────

export interface LanguageMeta {
  code: string;
  name: string;        // Native name (e.g. "Deutsch")
  englishName: string; // English name (e.g. "German")
  flag: string;        // Emoji flag
}

type TranslationMap = Record<string, string | Record<string, string | Record<string, string>>>;

interface I18nContextType {
  language: string;
  setLanguage: (code: string) => Promise<void>;
  t: (key: string, fallback?: string) => string;
  languages: LanguageMeta[];
  loading: boolean;
}

// ── Available Languages ──────────────────────────────────────────

export const AVAILABLE_LANGUAGES: LanguageMeta[] = [
  { code: 'en', name: 'English',    englishName: 'English',    flag: '🇬🇧' },
  { code: 'de', name: 'Deutsch',    englishName: 'German',     flag: '🇩🇪' },
  { code: 'it', name: 'Italiano',   englishName: 'Italian',    flag: '🇮🇹' },
  { code: 'fr', name: 'Français',   englishName: 'French',     flag: '🇫🇷' },
  { code: 'es', name: 'Español',    englishName: 'Spanish',    flag: '🇪🇸' },
  { code: 'pt', name: 'Português',  englishName: 'Portuguese', flag: '🇵🇹' },
  { code: 'pl', name: 'Polski',     englishName: 'Polish',     flag: '🇵🇱' },
  { code: 'da', name: 'Dansk',      englishName: 'Danish',     flag: '🇩🇰' },
  { code: 'no', name: 'Norsk',      englishName: 'Norwegian',  flag: '🇳🇴' },
  { code: 'sv', name: 'Svenska',    englishName: 'Swedish',    flag: '🇸🇪' },
  { code: 'uk', name: 'Українська', englishName: 'Ukrainian',  flag: '🇺🇦' },
  { code: 'hi', name: 'हिन्दी',      englishName: 'Hindi',      flag: '🇮🇳' },
  { code: 'zh', name: '中文',       englishName: 'Chinese',    flag: '🇨🇳' },
  { code: 'ja', name: '日本語',     englishName: 'Japanese',   flag: '🇯🇵' },
  { code: 'ko', name: '한국어',     englishName: 'Korean',     flag: '🇰🇷' },
];

// ── Language pack cache ──────────────────────────────────────────

const packCache: Record<string, TranslationMap> = {};
const packPromises: Partial<Record<string, Promise<TranslationMap>>> = {};

// Dynamic import map — Vite requires static patterns for glob imports
const packModules = import.meta.glob('./*.json', {
  import: 'default',
}) as Record<string, () => Promise<TranslationMap>>;

async function loadPack(code: string): Promise<TranslationMap> {
  if (packCache[code]) return packCache[code];
  if (packPromises[code]) return packPromises[code];

  const key = `./${code}.json`;
  const loader = packModules[key];
  if (!loader) {
    console.warn(`[i18n] Language pack not found: ${code}, falling back to English`);
    if (code !== 'en') return loadPack('en');
    return {};
  }

  const promise = loader()
    .then(pack => {
      packCache[code] = pack;
      return pack;
    })
    .catch(error => {
      console.error(`[i18n] Failed to load language pack: ${code}`, error);
      if (code !== 'en') return loadPack('en');
      return {};
    })
    .finally(() => {
      delete packPromises[code];
    });
  packPromises[code] = promise;
  return promise;
}

// ── Deep key resolution (supports "nav.overview" dot-notation) ───

function resolveKey(translations: TranslationMap, key: string): string | undefined {
  const parts = key.split('.');
  let current: unknown = translations;

  for (const part of parts) {
    if (current == null || typeof current !== 'object') return undefined;
    current = (current as Record<string, unknown>)[part];
  }

  return typeof current === 'string' ? current : undefined;
}

// ── Context ──────────────────────────────────────────────────────

const I18nContext = createContext<I18nContextType>({
  language: 'en',
  setLanguage: async () => {},
  t: (key: string) => key,
  languages: AVAILABLE_LANGUAGES,
  loading: false,
});

// ── Provider ─────────────────────────────────────────────────────

interface I18nProviderProps {
  children: ReactNode;
}

export const I18nProvider: React.FC<I18nProviderProps> = ({ children }) => {
  const [initialLanguage] = useState(() => localStorage.getItem('shogun_language') || 'en');
  const [language, setLanguageState] = useState<string>(initialLanguage);
  const [translations, setTranslations] = useState<TranslationMap>({});
  const [englishFallback, setEnglishFallback] = useState<TranslationMap>({});
  const [loading, setLoading] = useState(true);
  const packRequest = useRef(0);

  useEffect(() => {
    let active = true;
    const request = ++packRequest.current;
    Promise.all([loadPack(initialLanguage), loadPack('en')]).then(([pack, english]) => {
      if (!active || request !== packRequest.current) return;
      setTranslations(pack);
      setEnglishFallback(english);
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [initialLanguage]);

  const setLanguage = useCallback(async (code: string) => {
    const request = ++packRequest.current;
    setLoading(true);
    const [pack, english] = await Promise.all([loadPack(code), loadPack('en')]);
    if (request !== packRequest.current) return;
    localStorage.setItem('shogun_language', code);
    setTranslations(pack);
    setEnglishFallback(english);
    setLanguageState(code);
    setLoading(false);

    // Persist to backend (non-blocking)
    try {
      await fetch('/api/v1/i18n/active', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language: code }),
      });
    } catch {
      // Non-critical — localStorage is the primary store
    }
  }, []);

  const t = useCallback((key: string, fallback?: string): string => {
    // Try active language first
    const value = resolveKey(translations, key);
    if (value) return value;

    // Fall back to English
    const enValue = resolveKey(englishFallback, key);
    if (enValue) return enValue;

    // Last resort: return the fallback string or the key itself
    return fallback || key.split('.').pop() || key;
  }, [translations, englishFallback]);

  return React.createElement(
    I18nContext.Provider,
    {
      value: {
        language,
        setLanguage,
        t,
        languages: AVAILABLE_LANGUAGES,
        loading,
      },
    },
    children
  );
};

// ── Hook ─────────────────────────────────────────────────────────

export const useTranslation = (): I18nContextType => {
  return useContext(I18nContext);
};
