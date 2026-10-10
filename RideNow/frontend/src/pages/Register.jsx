import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Eye, EyeOff, UserPlus, Loader2, User, Car, Info, Sparkles, ArrowRight, ShieldCheck } from 'lucide-react';
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

const Register = () => {
  const { register, loginGoogle } = useAuth();
  const navigate = useNavigate();

  const [role, setRole] = useState('passenger');
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    password: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [googleConfig, setGoogleConfig] = useState({ configured: false, client_id: null });

  useEffect(() => {
    getGoogleOAuthConfig()
      .then((cfg) => setGoogleConfig(cfg))
      .catch(() => {});
  }, []);

  const handleGoogleCredentialResponse = useCallback(
    async (response) => {
      if (!response.credential) return;
      setGoogleLoading(true);
      try {
        const user = await loginGoogle(response.credential, role);
        toast.success(`Welcome to RideNow, ${user.name}!`);
        navigate(user.role === 'driver' ? '/driver/dashboard' : '/dashboard');
      } catch (err) {
        toast.error(getErrorMessage(err, 'Google registration failed'));
      } finally {
        setGoogleLoading(false);
      }
    },
    [loginGoogle, navigate, role]
  );

  const handleGoogleRegister = () => {
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
      window.google.accounts.id.initialize({
        client_id: googleConfig.client_id,
        callback: handleGoogleCredentialResponse,
      });
      window.google.accounts.id.prompt();
    } else {
      toast.error('Google Sign-In is initializing. Please try again in a moment.');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name || !formData.email || !formData.phone || !formData.password) {
      toast.error('Please fill in all fields');
      return;
    }

    setLoading(true);
    try {
      await register({ ...formData, role });
      toast.success('Account created successfully! Please sign in.');
      navigate('/login');
    } catch (err) {
      toast.error(getErrorMessage(err, 'Failed to create account'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative overflow-hidden rounded-3xl bg-gradient-to-b from-[#0D141B]/95 to-[#080E14]/98 p-8 md:p-9 shadow-float border border-[#1E293B]/80 text-[#F5F7FA] backdrop-blur-xl animate-fade-in max-h-[92vh] overflow-y-auto no-scrollbar">
      {/* Light bar on card top */}
      <div className="absolute top-0 left-1/4 right-1/4 h-[1px] bg-gradient-to-r from-transparent via-[#38BDF8]/60 to-transparent" />

      <div className="mb-5 space-y-1.5">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#38BDF8]/10 border border-[#38BDF8]/25 text-[#38BDF8] text-[11px] font-semibold tracking-wide">
          <Sparkles size={12} />
          <span>Next-Gen Urban Transit</span>
        </div>
        <h2 className="text-2xl font-bold text-[#F5F7FA] tracking-tight">Create your account</h2>
        <p className="text-xs text-gray-400">Join the AI-orchestrated urban mobility network.</p>
      </div>

      {/* Role Switcher */}
      <div className="grid grid-cols-2 gap-2 p-1 bg-[#101820] border border-[#1E293B] rounded-xl mb-5">
        <button
          type="button"
          onClick={() => setRole('passenger')}
          className={`flex items-center justify-center gap-2 py-2.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
            role === 'passenger'
              ? 'bg-[#38BDF8] text-[#05070A] shadow-sm'
              : 'text-gray-400 hover:text-[#F5F7FA]'
          }`}
        >
          <User size={15} /> Passenger
        </button>
        <button
          type="button"
          onClick={() => setRole('driver')}
          className={`flex items-center justify-center gap-2 py-2.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
            role === 'driver'
              ? 'bg-[#38BDF8] text-[#05070A] shadow-sm'
              : 'text-gray-400 hover:text-[#F5F7FA]'
          }`}
        >
          <Car size={15} /> Fleet Driver
        </button>
      </div>

      {/* Continue with Google */}
      <button
        type="button"
        onClick={handleGoogleRegister}
        disabled={googleLoading}
        className="w-full h-11 rounded-xl bg-[#101820] border border-[#1E293B] hover:border-[#38BDF8]/50 hover:bg-[#15222E] transition-all flex items-center justify-center gap-3 text-xs font-semibold text-[#F5F7FA] shadow-sm mb-4 active:scale-[0.99] group cursor-pointer"
      >
        {googleLoading ? (
          <Loader2 className="animate-spin text-[#38BDF8]" size={16} />
        ) : (
          <>
            <GoogleIcon />
            <span>Sign up with Google ({role === 'driver' ? 'Driver' : 'Passenger'})</span>
            <ArrowRight size={13} className="text-gray-500 group-hover:text-[#38BDF8] group-hover:translate-x-0.5 transition-all ml-auto pr-1" />
          </>
        )}
      </button>

      {/* Divider */}
      <div className="relative flex items-center justify-center mb-4">
        <div className="border-t border-[#1E293B] w-full" />
        <span className="bg-[#0A0F14] px-3 text-[11px] uppercase font-mono tracking-widest text-gray-500 shrink-0">
          or fill registration details
        </span>
        <div className="border-t border-[#1E293B] w-full" />
      </div>

      <form onSubmit={handleSubmit} className="space-y-3.5">
        <div>
          <label className="block text-[11px] font-semibold uppercase tracking-wider text-gray-400 mb-1" htmlFor="name">
            Full Name
          </label>
          <input
            id="name"
            type="text"
            required
            className="input-field py-2 text-xs"
            placeholder="Jane Doe"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          />
        </div>

        <div>
          <label className="block text-[11px] font-semibold uppercase tracking-wider text-gray-400 mb-1" htmlFor="email">
            Email address
          </label>
          <input
            id="email"
            type="email"
            required
            className="input-field py-2 text-xs"
            placeholder="jane@example.com"
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
          />
        </div>

        <div>
          <label className="block text-[11px] font-semibold uppercase tracking-wider text-gray-400 mb-1" htmlFor="phone">
            Phone Number
          </label>
          <input
            id="phone"
            type="tel"
            required
            className="input-field py-2 text-xs"
            placeholder="+91 98765 43210"
            value={formData.phone}
            onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
          />
        </div>

        <div>
          <label className="block text-[11px] font-semibold uppercase tracking-wider text-gray-400 mb-1" htmlFor="password">
            Password
          </label>
          <div className="relative">
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              required
              className="input-field py-2 pr-10 text-xs"
              placeholder="••••••••"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
            />
            <button
              type="button"
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors focus:outline-none cursor-pointer"
              onClick={() => setShowPassword(!showPassword)}
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>

        {role === 'driver' && (
          <div className="p-3 bg-[#101820] border border-[#38BDF8]/25 text-[#38BDF8] rounded-xl text-xs flex gap-2">
            <ShieldCheck size={16} className="shrink-0 mt-0.5 text-[#38BDF8]" />
            <p className="text-[11px] text-gray-300">
              Fleet driver verification will be finalized during initial onboarding.
            </p>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="btn btn-primary w-full mt-3 h-11 text-xs font-semibold uppercase tracking-wider shadow-[0_0_20px_rgba(56,189,248,0.25)] cursor-pointer"
        >
          {loading ? (
            <Loader2 className="animate-spin text-[#05070A]" size={18} />
          ) : (
            <>
              <UserPlus size={16} className="mr-2" />
              Complete Registration
            </>
          )}
        </button>
      </form>

      <div className="mt-5 text-center text-xs text-gray-400">
        Already have an account?{' '}
        <Link to="/login" className="font-semibold text-[#38BDF8] hover:underline">
          Sign in
        </Link>
      </div>
    </div>
  );
};

export default Register;
