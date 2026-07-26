import axios from 'axios';

const api = axios.create({
  baseURL: '/api/gensui',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

function cookie(name: string): string | null {
  const prefix = `${name}=`;
  const value = document.cookie.split('; ').find((part) => part.startsWith(prefix));
  return value ? decodeURIComponent(value.slice(prefix.length)) : null;
}

api.interceptors.request.use((config) => {
  const method = (config.method || 'get').toUpperCase();
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const csrf = cookie('gensui_csrf_token');
    if (csrf) config.headers['X-CSRF-Token'] = csrf;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const request = error.config;
    const url = String(request?.url || '');
    if (error.response?.status === 401 && request && !request._retry && !url.includes('/auth/login') && !url.includes('/auth/refresh')) {
      request._retry = true;
      try {
        await api.post('/auth/refresh');
        return api(request);
      } catch {
        localStorage.removeItem('gensui_token');
        localStorage.removeItem('gensui_admin');
        sessionStorage.removeItem('gensui_admin');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;
