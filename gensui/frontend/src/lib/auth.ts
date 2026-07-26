export function getAdmin(): Record<string, string> | null {
  const raw = sessionStorage.getItem('gensui_admin');
  return raw ? JSON.parse(raw) : null;
}

export function setAuth(admin: Record<string, string>): void {
  sessionStorage.setItem('gensui_admin', JSON.stringify(admin));
}

export function clearAuth(): void {
  localStorage.removeItem('gensui_token'); // remove legacy bearer storage
  localStorage.removeItem('gensui_admin');
  sessionStorage.removeItem('gensui_admin');
}

export function isAuthenticated(): boolean {
  return !!getAdmin();
}
