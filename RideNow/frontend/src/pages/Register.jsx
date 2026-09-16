import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Eye, EyeOff, UserPlus, Loader2, User, Car } from 'lucide-react';
import toast from 'react-hot-toast';
import { getErrorMessage } from '../services/api';

const Register = () => {
  const { register } = useAuth();
  const navigate = useNavigate();
  
  const [role, setRole] = useState('passenger');
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    password: ''
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name || !formData.email || !formData.phone || !formData.password) {
      toast.error('Please fill in all fields');
      return;
    }

    setLoading(true);
    try {
      await register({ ...formData, role });
      toast.success('Account created successfully! Please log in.');
      navigate('/login');
    } catch (err) {
      toast.error(getErrorMessage(err, 'Failed to create account'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white p-8 rounded-3xl shadow-float border border-gray-100 max-h-[90vh] overflow-y-auto no-scrollbar">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Create an account</h2>
        <p className="text-gray-500">Join RideNow to get started.</p>
      </div>

      {/* Segmented Control for Role */}
      <div className="flex p-1 bg-gray-100 rounded-xl mb-6">
        <button
          type="button"
          onClick={() => setRole('passenger')}
          className={`flex-1 flex items-center justify-center gap-2 py-2 text-sm font-medium rounded-lg transition-all ${
            role === 'passenger' 
              ? 'bg-white text-brand-950 shadow-sm' 
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <User size={16} /> Passenger
        </button>
        <button
          type="button"
          onClick={() => setRole('driver')}
          className={`flex-1 flex items-center justify-center gap-2 py-2 text-sm font-medium rounded-lg transition-all ${
            role === 'driver' 
              ? 'bg-white text-brand-950 shadow-sm' 
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          <Car size={16} /> Driver
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="name">
            Full Name
          </label>
          <input
            id="name"
            type="text"
            required
            className="input-field py-2.5"
            placeholder="John Doe"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="email">
            Email address
          </label>
          <input
            id="email"
            type="email"
            required
            className="input-field py-2.5"
            placeholder="john@example.com"
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="phone">
            Phone Number
          </label>
          <input
            id="phone"
            type="tel"
            required
            className="input-field py-2.5"
            placeholder="+1 (555) 000-0000"
            value={formData.phone}
            onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="password">
            Password
          </label>
          <div className="relative">
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              required
              className="input-field py-2.5 pr-12"
              placeholder="••••••••"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
            />
            <button
              type="button"
              className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 focus:outline-none"
              onClick={() => setShowPassword(!showPassword)}
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
        </div>

        {role === 'driver' && (
          <div className="p-3 bg-blue-50 text-blue-800 rounded-lg text-sm flex gap-2">
            <Car size={20} className="shrink-0" />
            <p>You'll need to complete your vehicle profile after registration to start driving.</p>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="btn btn-primary w-full mt-2 h-11"
        >
          {loading ? (
            <Loader2 className="animate-spin" size={20} />
          ) : (
            <>
              <UserPlus size={18} className="mr-2" />
              Create account
            </>
          )}
        </button>
      </form>

      <div className="mt-6 text-center text-sm text-gray-600">
        Already have an account?{' '}
        <Link to="/login" className="font-medium text-brand-950 hover:underline">
          Sign in
        </Link>
      </div>
    </div>
  );
};

export default Register;
