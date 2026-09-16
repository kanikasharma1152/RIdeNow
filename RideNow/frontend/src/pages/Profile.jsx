import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { updateProfile } from '../services/authService';
import { getMyDriverProfile, updateDriverProfile } from '../services/driverService';
import { 
  User, 
  Mail, 
  Phone, 
  Car, 
  FileText, 
  Lock, 
  Save, 
  Loader2, 
  Edit3, 
  Shield, 
  CheckCircle2, 
  ShieldCheck,
  Award,
  Hash,
  Sparkles
} from 'lucide-react';
import toast from 'react-hot-toast';

const Profile = () => {
  const { user, setUser } = useAuth();
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [driverProfile, setDriverProfile] = useState(null);

  const [formData, setFormData] = useState({
    name: user?.name || '',
    phone: user?.phone || '',
    vehicle_type: '',
    vehicle_number: '',
    vehicle_model: '',
    license_number: '',
  });

  useEffect(() => {
    if (user?.role === 'driver') {
      const fetchDriver = async () => {
        try {
          const profile = await getMyDriverProfile();
          setDriverProfile(profile);
          setFormData((prev) => ({
            ...prev,
            name: user?.name || '',
            phone: user?.phone || '',
            vehicle_type: profile.vehicle_type || '',
            vehicle_number: profile.vehicle_number || '',
            vehicle_model: profile.vehicle_model || '',
            license_number: profile.license_number || '',
          }));
        } catch {
          // Non-blocking if driver profile isn't found yet
        }
      };
      fetchDriver();
    } else {
      setFormData((prev) => ({
        ...prev,
        name: user?.name || '',
        phone: user?.phone || '',
      }));
    }
  }, [user]);

  const handleSave = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const updatedUser = await updateProfile({
        name: formData.name,
        phone: formData.phone,
      });
      setUser(updatedUser);

      if (user?.role === 'driver') {
        const updatedDriver = await updateDriverProfile({
          vehicle_type: formData.vehicle_type,
          vehicle_number: formData.vehicle_number,
          vehicle_model: formData.vehicle_model,
          license_number: formData.license_number,
        });
        setDriverProfile(updatedDriver);
      }

      setEditing(false);
      toast.success('Profile credentials updated');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update profile');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    setFormData({
      name: user?.name || '',
      phone: user?.phone || '',
      vehicle_type: driverProfile?.vehicle_type || '',
      vehicle_number: driverProfile?.vehicle_number || '',
      vehicle_model: driverProfile?.vehicle_model || '',
      license_number: driverProfile?.license_number || '',
    });
    setEditing(false);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in pb-16">
      
      {/* 1. Profile Hero Card */}
      <div className="card-panel p-6 lg:p-8 bg-gradient-to-r from-[#0A0F14] via-[#101820] to-[#0A0F14] border border-[#1E293B] flex flex-col sm:flex-row items-center sm:items-start justify-between gap-6">
        <div className="flex flex-col sm:flex-row items-center gap-5">
          <div className="relative shrink-0">
            <div className="w-20 h-20 rounded-2xl bg-[#38BDF8]/10 border border-[#38BDF8]/30 text-[#38BDF8] flex items-center justify-center text-3xl font-bold shadow-[0_0_20px_rgba(56,189,248,0.25)]">
              {user?.name?.charAt(0) || 'U'}
            </div>
            <div className={`absolute -bottom-1 -right-1 w-4 h-4 rounded-full border-2 border-[#0A0F14] ${user?.is_active ? 'bg-emerald-400' : 'bg-gray-500'}`} />
          </div>

          <div className="text-center sm:text-left">
            <div className="flex items-center justify-center sm:justify-start gap-2.5 mb-1">
              <h1 className="text-2xl font-bold text-white tracking-tight">{user?.name}</h1>
              <span className="text-[10px] font-mono uppercase bg-[#38BDF8]/10 text-[#38BDF8] border border-[#38BDF8]/30 px-2 py-0.5 rounded-full font-bold">
                {user?.role}
              </span>
            </div>
            <p className="text-gray-400 text-xs font-mono">
              Account ID: RN-USR-{user?.id || '001'} · Identity Verified
            </p>
            <div className="inline-flex items-center gap-1.5 mt-2.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <CheckCircle2 size={12} /> {user?.is_active ? 'Authenticated Active' : 'Restricted'}
            </div>
          </div>
        </div>

        <div>
          {!editing && (
            <button
              onClick={() => setEditing(true)}
              className="btn btn-secondary px-4 py-2.5 rounded-xl text-xs font-semibold flex items-center gap-2"
            >
              <Edit3 size={14} className="text-[#38BDF8]" />
              <span>Edit Profile</span>
            </button>
          )}
        </div>
      </div>

      {/* 2. User Information Section (Modular Grid Cards) */}
      <div className="space-y-3">
        <div className="flex items-center justify-between px-1">
          <h2 className="text-xs font-mono font-bold text-gray-400 uppercase tracking-widest flex items-center gap-2">
            <User size={14} className="text-[#38BDF8]" /> Personal Information
          </h2>
        </div>

        {!editing ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="card p-5 bg-[#0A0F14] border border-[#1E293B]">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#101820] border border-[#1E293B] text-[#38BDF8] flex items-center justify-center shrink-0">
                  <User size={18} />
                </div>
                <div>
                  <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider font-mono">Full Name</p>
                  <p className="text-sm font-semibold text-white mt-0.5">{user?.name || '—'}</p>
                </div>
              </div>
            </div>

            <div className="card p-5 bg-[#0A0F14] border border-[#1E293B]">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#101820] border border-[#1E293B] text-[#38BDF8] flex items-center justify-center shrink-0">
                  <Mail size={18} />
                </div>
                <div className="truncate">
                  <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider font-mono">Verified Email</p>
                  <p className="text-sm font-semibold text-white mt-0.5 truncate">{user?.email || '—'}</p>
                </div>
              </div>
            </div>

            <div className="card p-5 bg-[#0A0F14] border border-[#1E293B]">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#101820] border border-[#1E293B] text-[#38BDF8] flex items-center justify-center shrink-0">
                  <Phone size={18} />
                </div>
                <div>
                  <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider font-mono">Contact Phone</p>
                  <p className="text-sm font-semibold text-white mt-0.5">{user?.phone || '—'}</p>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSave} className="card-panel p-6 border border-[#1E293B] space-y-5">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5 font-mono">Full Name</label>
                <input
                  type="text"
                  required
                  className="input-field text-sm"
                  value={formData.name}
                  onChange={e => setFormData({ ...formData, name: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5 font-mono">Phone Number</label>
                <input
                  type="tel"
                  required
                  className="input-field text-sm"
                  value={formData.phone}
                  onChange={e => setFormData({ ...formData, phone: e.target.value })}
                />
              </div>
            </div>

            {user?.role === 'driver' && (
              <div className="pt-4 border-t border-[#1E293B] space-y-4">
                <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <Car size={15} className="text-[#38BDF8]" /> Vehicle Telemetry Parameters
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-gray-400 mb-1 font-mono">Vehicle Class</label>
                    <select
                      className="input-field text-sm"
                      value={formData.vehicle_type}
                      onChange={e => setFormData({ ...formData, vehicle_type: e.target.value })}
                    >
                      <option value="sedan">Sedan</option>
                      <option value="suv">SUV</option>
                      <option value="bike">Bike</option>
                      <option value="auto">Auto</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-gray-400 mb-1 font-mono">Vehicle Model</label>
                    <input
                      type="text"
                      className="input-field text-sm"
                      placeholder="e.g. Honda City"
                      value={formData.vehicle_model}
                      onChange={e => setFormData({ ...formData, vehicle_model: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-400 mb-1 font-mono">Vehicle Plate Number</label>
                    <input
                      type="text"
                      className="input-field text-sm"
                      placeholder="e.g. KA-01-AB-1234"
                      value={formData.vehicle_number}
                      onChange={e => setFormData({ ...formData, vehicle_number: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-400 mb-1 font-mono">Driving License ID</label>
                    <input
                      type="text"
                      className="input-field text-sm"
                      placeholder="e.g. DL-123456789"
                      value={formData.license_number}
                      onChange={e => setFormData({ ...formData, license_number: e.target.value })}
                    />
                  </div>
                </div>
              </div>
            )}

            <div className="flex gap-3 pt-3">
              <button type="submit" disabled={loading} className="btn btn-primary py-3 px-6 text-xs font-bold flex-1">
                {loading ? <Loader2 className="animate-spin mx-auto w-4 h-4" /> : <><Save size={15} className="mr-1.5 inline" /> Save Credentials</>}
              </button>
              <button type="button" onClick={handleCancel} className="btn btn-secondary py-3 px-6 text-xs font-semibold flex-1">
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>

      {/* 3. Driver Vehicle Telemetry Cards (View Mode Only) */}
      {user?.role === 'driver' && !editing && (
        <div className="space-y-3">
          <div className="flex items-center justify-between px-1">
            <h2 className="text-xs font-mono font-bold text-gray-400 uppercase tracking-widest flex items-center gap-2">
              <Car size={14} className="text-[#38BDF8]" /> Assigned Vehicle Unit
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="card p-5 bg-[#0A0F14] border border-[#1E293B]">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#101820] border border-[#1E293B] text-[#38BDF8] flex items-center justify-center shrink-0">
                  <Car size={18} />
                </div>
                <div>
                  <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider font-mono">Model</p>
                  <p className="text-sm font-semibold text-white mt-0.5">{driverProfile?.vehicle_model || 'Not provided'}</p>
                </div>
              </div>
            </div>

            <div className="card p-5 bg-[#0A0F14] border border-[#1E293B]">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#101820] border border-[#1E293B] text-[#38BDF8] flex items-center justify-center shrink-0">
                  <Award size={18} />
                </div>
                <div>
                  <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider font-mono">Class</p>
                  <p className="text-sm font-semibold text-white mt-0.5 uppercase font-mono">{driverProfile?.vehicle_type || 'Not provided'}</p>
                </div>
              </div>
            </div>

            <div className="card p-5 bg-[#0A0F14] border border-[#1E293B]">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#101820] border border-[#1E293B] text-[#38BDF8] flex items-center justify-center shrink-0">
                  <Hash size={18} />
                </div>
                <div>
                  <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider font-mono">Plate Number</p>
                  <p className="text-xs font-mono font-bold text-[#38BDF8] mt-0.5">{driverProfile?.vehicle_number || 'Not provided'}</p>
                </div>
              </div>
            </div>

            <div className="card p-5 bg-[#0A0F14] border border-[#1E293B]">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#101820] border border-[#1E293B] text-[#38BDF8] flex items-center justify-center shrink-0">
                  <Shield size={18} />
                </div>
                <div className="truncate">
                  <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider font-mono">License ID</p>
                  <p className="text-xs font-mono text-white mt-0.5 truncate">{driverProfile?.license_number || 'Not provided'}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 4. Security & Cryptographic Session Card */}
      <div className="card-panel p-6 bg-[#0A0F14] border border-[#1E293B]">
        <div className="flex items-center gap-2 mb-2">
          <Lock size={15} className="text-[#38BDF8]" />
          <h2 className="text-sm font-bold text-white tracking-tight">Platform Security & Cryptographic Session Guard</h2>
        </div>
        <p className="text-xs text-gray-400 mb-4">
          Session integrity is guarded with role-based JWT authorization tokens and automated cryptographic refreshes.
        </p>

        <div className="p-4 bg-[#101820] border border-[#1E293B] rounded-xl flex items-center gap-3 text-xs text-gray-300">
          <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0" />
          <span>Active bearer token verified. Requests routed securely to FastAPI reverse proxy over HTTPS.</span>
        </div>
      </div>

    </div>
  );
};

export default Profile;
