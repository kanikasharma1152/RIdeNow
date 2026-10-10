import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Eye, EyeOff, LogIn, Loader2, Info, Sparkles, Bot, Shield, ArrowRight } from 'lucide-react';
import toast from 'react-hot-toast';
import { getErrorMessage } from '../services/api';
import { getGoogleOAuthConfig } from '../services/authService';

const GoogleIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" className="shrink-0">
    <path
      fill="#4285F4"
      d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17z"
    />
    <path
      fill="#34A853"
      d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.26v3.15C3.26 21.36 7.33 24 12 24z"
    />
    <path
      fill="#FBBC05"
      d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.26C.46 8.17 0 9.99 0 12s.46 3.83 1.26 5.42l4.02-3.15z"
    />
    <path
      fill="#EA4335"
      d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.26 2.64 1.26 6.58l4.02 3.15c.95-2.83 3.6-4.98 6.72-4.98z"
    />
  </svg>
);

const getHomeRouteForRole = (role) => {
  if (role === 'admin') return '/admin/dashboard';
  if (role === 'driver') return '/driver/dashboard';
  return '/dashboard';
};

const Login = () => {
  const { login, loginGoogle } = useAuth();
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [googleConfig, setGoogleConfig] = useState({ configured: false, client_id: null });

  // Typewriter Nova greeting
  const [greetingText, setGreetingText] = useState('');
  const fullGreeting = "Hello, I'm Nova. Ready to take you anywhere.";

  useEffect(() => {
    let i = 0;
    const interval = setInterval(() => {
      if (i <= fullGreeting.length) {
        setGreetingText(fullGreeting.slice(0, i));
        i++;
      } else {
        clearInterval(interval);
      }
    }, 40);
    return () => clearInterval(interval);
  }, []);

  // Check Google OAuth availability from backend
  useEffect(() => {
    getGoogleOAuthConfig()
      .then((cfg) => {
        setGoogleConfig(cfg);
        if (cfg.configured && cfg.client_id) {
          loadGoogleScript(cfg.client_id);
        }
      })
      .catch(() => {
        // Fallback: oauth config endpoint optional in offline/dev mode
      });
  }, []);

  const handleGoogleCredentialResponse = useCallback(
    async (response) => {
      if (!response.credential) return;
      setGoogleLoading(true);
      try {
        const user = await loginGoogle(response.credential, 'passenger');
        toast.success(`Welcome back, ${user.name}!`);
        navigate(getHomeRouteForRole(user.role));
      } catch (err) {
        toast.error(getErrorMessage(err, 'Google authentication failed'));
      } finally {
        setGoogleLoading(false);
      }
    },
    [loginGoogle, navigate]
  );

  const loadGoogleScript = (clientId) => {
    if (window.google?.accounts?.id) {
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: handleGoogleCredentialResponse,
      });
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.onload = () => {
      window.google?.accounts?.id?.initialize({
        client_id: clientId,
        callback: handleGoogleCredentialResponse,
      });
    };
    document.body.appendChild(script);
  };

  const handleGoogleLogin = () => {
    if (!googleConfig.configured) {
      toast(
        (t) => (
          <div className="flex flex-col gap-1 text-xs">
            <span className="font-semibold text-white">Google OAuth Architecture Ready</span>
            <span className="text-gray-300">
              Set <code className="bg-black/40 px-1 py-0.5 rounded text-[#38BDF8]">GOOGLE_CLIENT_ID</code> in <code className="bg-black/40 px-1 py-0.5 rounded text-[#38BDF8]">backend/.env</code> to activate live Google Sign-In.
            </span>
          </div>
        ),
        {
          duration: 6000,
          icon: <Info size={18} className="text-[#38BDF8]" />,
          style: {
            background: '#101820',
            border: '1px solid #1E293B',
            color: '#F5F7FA',
          },
        }
      );
      return;
    }

    if (window.google?.accounts?.id) {
      window.google.accounts.id.prompt();
    } else {
      toast.error('Google Sign-In is initializing. Please try again in a moment.');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.email || !formData.password) {
      toast.error('Please enter both email and password');
      return;
    }

    setLoading(true);
    try {
      const loggedUser = await login(formData.email, formData.password);
      toast.success('Welcome back!');
      navigate(getHomeRouteForRole(loggedUser?.role));
    } catch (err) {
      toast.error(getErrorMessage(err, 'Invalid email or password'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative overflow-hidden rounded-3xl bg-gradient-to-b from-[#0D141B]/95 to-[#080E14]/98 p-8 md:p-9 shadow-float border border-[#1E293B]/80 text-[#F5F7FA] backdrop-blur-xl animate-fade-in">
      {/* Subtle ambient light bar at top */}
      <div className="absolute top-0 left-1/4 right-1/4 h-[1px] bg-gradient-to-r from-transparent via-[#38BDF8]/60 to-transparent" />

      {/* ── Nova AI Cinematic Header ───────────────────────────────────── */}
      <div className="mb-6 space-y-2">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#38BDF8]/10 border border-[#38BDF8]/25 text-[#38BDF8] text-[11px] font-semibold tracking-wide">
          <Bot size={13} className="animate-pulse" />
          <span>Nova AI Mobility Terminal</span>
        </div>

        <h2 className="text-2xl font-bold tracking-tight text-[#F5F7FA]">
          Welcome Back
        </h2>

        <p className="text-xs text-gray-400 font-mono h-5 flex items-center gap-1">
          <span>{greetingText}</span>
          <span className="w-1.5 h-3.5 bg-[#38BDF8] inline-block animate-pulse" />
        </p>
      </div>

      {/* ── Google OAuth Button (Primary Action) ──────────────────────── */}
      <button
        type="button"
        onClick={handleGoogleLogin}
        disabled={googleLoading}
        className="w-full h-12 rounded-xl bg-[#101820] border border-[#1E293B] hover:border-[#38BDF8]/50 hover:bg-[#15222E] transition-all flex items-center justify-center gap-3 text-sm font-semibold text-[#F5F7FA] shadow-sm mb-5 group active:scale-[0.99] cursor-pointer"
      >
        {googleLoading ? (
          <Loader2 className="animate-spin text-[#38BDF8]" size={18} />
        ) : (
          <>
            <GoogleIcon />
            <span>Continue with Google</span>
            <ArrowRight size={14} className="text-gray-500 group-hover:text-[#38BDF8] group-hover:translate-x-0.5 transition-all ml-auto pr-1" />
          </>
        )}
      </button>

      {/* ── Divider ────────────────────────────────────────────────────── */}
      <div className="relative flex items-center justify-center mb-5">
        <div className="border-t border-[#1E293B] w-full" />
        <span className="bg-[#0A0F14] px-3 text-[11px] uppercase font-mono tracking-widest text-gray-500 shrink-0">
          or sign in with credentials
        </span>
        <div className="border-t border-[#1E293B] w-full" />
      </div>

      {/* ── Standard Email / Password Form ────────────────────────────── */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1.5" htmlFor="email">
            Email address
          </label>
          <input
            id="email"
            type="email"
            required
            className="input-field text-sm"
            placeholder="name@example.com"
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
          />
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1.5" htmlFor="password">
            Password
          </label>
          <div className="relative">
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              required
              className="input-field pr-12 text-sm"
              placeholder="••••••••"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
            />
            <button
              type="button"
              className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors focus:outline-none cursor-pointer"
              onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between pt-1">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              className="w-4 h-4 rounded bg-[#0D141B] border-[#1E293B] text-[#38BDF8] focus:ring-[#38BDF8]/20 cursor-pointer"
            />
            <span className="text-xs text-gray-400">Remember credentials</span>
          </label>
          <span className="text-xs text-[#38BDF8] hover:underline cursor-pointer">
            Forgot password?
          </span>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="btn btn-primary w-full mt-4 h-12 text-sm font-semibold tracking-wide shadow-[0_0_20px_rgba(56,189,248,0.25)] cursor-pointer"
        >
          {loading ? (
            <Loader2 className="animate-spin text-[#05070A]" size={18} />
          ) : (
            <>
              <LogIn size={18} className="mr-2" />
              Sign into RideNow
            </>
          )}
        </button>
      </form>

      <div className="mt-6 text-center text-xs text-gray-400">
        New to RideNow?{' '}
        <Link to="/register" className="font-semibold text-[#38BDF8] hover:underline">
          Create account
        </Link>
      </div>
    </div>
  );
};

export default Login;
