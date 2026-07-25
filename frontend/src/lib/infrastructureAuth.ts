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
