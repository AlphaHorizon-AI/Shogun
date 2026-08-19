import { useState } from 'react';
import { useNavigate } from '../lib/routerCompat';
import axios from 'axios';
import { Eye, EyeOff } from 'lucide-react';
import api from '../lib/api';
import { setAuth } from '../lib/auth';
import { useTranslation } from '../i18n';

export default function Login() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const { data } = await api.post('/auth/login', { email, password });
      setAuth(data.admin);
      navigate('/');
    } catch (err: unknown) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : undefined;
      setError(typeof detail === 'string' ? detail : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      {/* Background Effects */}
      <div className="fixed inset-0 bg-gensui-900">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--color-crimson-900)_0%,_transparent_70%)] opacity-20"></div>
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,_var(--color-amber-900)_0%,_transparent_60%)] opacity-10"></div>
      </div>

      {/* Login Card */}
      <div className="relative glass-card p-8 w-full max-w-md">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <img src="/gensui-purple-logo.png" alt="Gensui" className="w-20 h-20 rounded-2xl mb-4 danger-glow" />
          <h1 className="text-2xl font-bold text-gensui-50 tracking-wider">GENSUI</h1>
          <p className="text-xs text-gensui-500 uppercase tracking-[0.3em] mt-1">Central Command</p>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 p-3 rounded-xl bg-crimson-900/30 border border-crimson-700/30 text-crimson-300 text-sm">
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-xs text-gensui-400 uppercase tracking-wider mb-1.5">{t('auth.email_label', 'Email')}</label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="gensui-input"
              placeholder="admin@gensui.local"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-gensui-400 uppercase tracking-wider mb-1.5">{t('auth.password_label', 'Password')}</label>
            <div className="relative">
              <input
                id="login-password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="gensui-input pr-10"
                placeholder="••••••••"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gensui-500 hover:text-gensui-300"
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>
          <button
            id="login-submit"
            type="submit"
            disabled={loading}
            className="btn-primary w-full py-3 text-sm"
          >
            {loading ? t('auth.signing_in', 'Authenticating...') : t('auth.sign_in', 'Access Command Center')}
          </button>
        </form>

        <p className="text-center text-xs text-gensui-600 mt-6">
          Secured by Gensui Security Protocol v0.1
        </p>
      </div>
    </div>
  );
}
