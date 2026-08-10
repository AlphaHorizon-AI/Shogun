import axios from 'axios';

const STORAGE_KEY = 'shogun.infrastructureAdminToken';

export function getInfrastructureAdminToken(): string {
  if (typeof window === 'undefined') return '';
  return window.sessionStorage.getItem(STORAGE_KEY) || '';
}

export function setInfrastructureAdminToken(token: string): void {
  if (typeof window === 'undefined') return;
  if (token) {
    window.sessionStorage.setItem(STORAGE_KEY, token);
  } else {
    window.sessionStorage.removeItem(STORAGE_KEY);
  }
}

export function infrastructureRequestConfig(token: string) {
  return token
    ? { headers: { 'X-Shogun-Infrastructure-Token': token } }
    : {};
}

export function consumeInfrastructureTokenFromLocation(): void {
  if (typeof window === 'undefined' || !window.location.hash) return;
  const params = new URLSearchParams(window.location.hash.slice(1));
  const token = params.get('infrastructure_token');
  if (!token) return;
  setInfrastructureAdminToken(token);
  window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}`);
}

export function installInfrastructureFetchGuard(): void {
  if (typeof window === 'undefined') return;
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input: RequestInfo | URL, init: RequestInit = {}) => {
    const target = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    const url = new URL(target, window.location.origin);
    const token = getInfrastructureAdminToken();
    const protectedPath = url.pathname.startsWith('/api/v1/')
      || url.pathname.startsWith('/uploads/')
      || url.pathname.startsWith('/mado/screenshots/')
      || url.pathname.startsWith('/ronin/screenshots/');
    if (token && url.origin === window.location.origin && protectedPath) {
      const headers = new Headers(input instanceof Request ? input.headers : undefined);
      new Headers(init.headers).forEach((value, key) => headers.set(key, value));
      headers.set('X-Shogun-Infrastructure-Token', token);
      return originalFetch(input, { ...init, headers });
    }
    return originalFetch(input, init);
  };
  axios.interceptors.request.use(config => {
    const token = getInfrastructureAdminToken();
    const url = typeof config.url === 'string' ? new URL(config.url, window.location.origin) : null;
    const protectedPath = url?.pathname.startsWith('/api/v1/')
      || url?.pathname.startsWith('/uploads/')
      || url?.pathname.startsWith('/mado/screenshots/')
      || url?.pathname.startsWith('/ronin/screenshots/');
    if (token && url?.origin === window.location.origin && protectedPath) {
      config.headers.set('X-Shogun-Infrastructure-Token', token);
    }
    return config;
  });
}
