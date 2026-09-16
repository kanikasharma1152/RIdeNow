import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getRide, startRide, completeRide } from '../../services/rideService';
import Map from '../../components/Map';
import { Navigation, Loader2, Play, CheckCircle2, Navigation2, Check, User } from 'lucide-react';
import toast from 'react-hot-toast';

const STATUS_STEPS = ['ACCEPTED', 'STARTED', 'COMPLETED'];

const DriverRideStatusProgress = ({ currentStatus }) => {
  let currentIndex = STATUS_STEPS.indexOf(currentStatus);
  if (currentStatus === 'CANCELLED') currentIndex = 0;

  return (
    <div className="relative mb-8 mt-4 px-4">
      <div className="absolute top-1/2 left-4 right-4 h-1 bg-border-default -translate-y-1/2 rounded-full z-0"></div>
      
      {currentIndex >= 0 && currentStatus !== 'CANCELLED' && (
        <div 
          className="absolute top-1/2 left-4 h-1 bg-brand-500 -translate-y-1/2 rounded-full z-0 transition-all duration-500 ease-in-out shadow-glow"
          style={{ width: `${(currentIndex / (STATUS_STEPS.length - 1)) * 100}%` }}
        ></div>
      )}

      <div className="flex justify-between relative z-10">
        {STATUS_STEPS.map((step, index) => {
          const isActive = index <= currentIndex && currentStatus !== 'CANCELLED';
          const isCurrent = index === currentIndex && currentStatus !== 'CANCELLED';
          
          return (
            <div key={step} className="flex flex-col items-center">
              <div className={`w-4 h-4 rounded-full flex items-center justify-center transition-all duration-300 ${
                isActive ? 'bg-brand-500 scale-125 shadow-glow' : 'bg-bg-tertiary border border-border-default'
              }`}>
                {isActive && <div className="w-1.5 h-1.5 bg-white rounded-full"></div>}
              </div>
              <span className={`text-[10px] sm:text-xs font-mono font-bold mt-2 uppercase tracking-wider transition-colors duration-300 ${
                isCurrent ? 'text-brand-400' : isActive ? 'text-white' : 'text-gray-500'
              }`}>
                {step}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const DriverRideDetails = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  
  const [ride, setRide] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchRide = async () => {
    try {
      const data = await getRide(id);
      setRide(data);
    } catch (err) {
      toast.error('Failed to load ride');
      navigate('/driver/rides');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRide();
  }, [id]);

  const handleStartRide = async () => {
    setActionLoading(true);
    try {
      await startRide(id);
      toast.success('Ride started!');
      await fetchRide();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to start ride');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCompleteRide = async () => {
    setActionLoading(true);
    try {
      await completeRide(id);
      toast.success('Ride completed successfully!');
      await fetchRide();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to complete ride');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) return (
    <div className="flex h-[80vh] items-center justify-center">
      <Loader2 className="w-8 h-8 animate-spin text-brand-400" />
    </div>
  );
  if (!ride) return null;

  const markers = [];
  if (ride.pickup_latitude && ride.pickup_longitude) {
    markers.push({ lat: ride.pickup_latitude, lng: ride.pickup_longitude, type: 'pickup' });
  }

  const isCancelled = ride.status === 'CANCELLED';

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 max-w-6xl mx-auto min-h-[calc(100vh-140px)] animate-fade-in pb-20">
      
      {/* Left Column: Ride Info & Action Controls */}
      <div className="lg:col-span-5 flex flex-col gap-6">
        
        {/* Status Header & Stepper Card */}
        <div className="card-panel p-6 border border-[#1E293B] bg-[#0A0F14] rounded-2xl shadow-xl overflow-hidden">
          <div className="flex justify-between items-start mb-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-mono uppercase bg-[#101820] text-[#38BDF8] border border-[#38BDF8]/30 px-2.5 py-0.5 rounded-full flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8] animate-ping" />
                  Active Dispatch
                </span>
                <span className="text-xs text-gray-400 font-mono">#RN-{ride.id}</span>
              </div>
              <h2 className="text-2xl font-bold text-[#F5F7FA] mt-1">
                {isCancelled ? 'Ride Cancelled' : ride.status === 'COMPLETED' ? 'Ride Completed' : 'Active Ride'}
              </h2>
            </div>
            <div className="w-12 h-12 bg-[#38BDF8]/15 border border-[#38BDF8]/40 text-[#38BDF8] rounded-2xl flex items-center justify-center shadow-[0_0_15px_rgba(56,189,248,0.2)]">
              <Navigation2 size={24} />
            </div>
          </div>

          <DriverRideStatusProgress currentStatus={ride.status} />
        </div>

        {/* Route Corridor Card */}
        <div className="card p-6 border border-[#1E293B] bg-[#0A0F14] rounded-2xl shadow-lg">
          <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4 flex items-center gap-2">
            <Navigation size={14} className="text-[#38BDF8]" />
            Trip Route Corridor
          </h3>

          <div className="relative pl-1">
            <div className="absolute left-3.5 top-[24px] bottom-[24px] w-0.5 bg-[#1E293B] z-0"></div>
            
            <div className="relative z-10 flex gap-3.5 mb-5">
              <div className="w-7 h-7 bg-[#101820] border-2 border-[#38BDF8] rounded-full flex items-center justify-center shrink-0 shadow-[0_0_8px_rgba(56,189,248,0.4)]">
                <div className="w-2 h-2 bg-[#38BDF8] rounded-full"></div>
              </div>
              <div>
                <p className="text-[10px] font-mono font-bold text-gray-400 uppercase tracking-wider mb-0.5">Pickup Passenger</p>
                <p className="font-semibold text-[#F5F7FA] text-xs sm:text-sm">{ride.pickup_location}</p>
              </div>
            </div>

            <div className="relative z-10 flex gap-3.5">
              <div className="w-7 h-7 bg-[#10B981] border-2 border-[#10B981] rounded-full flex items-center justify-center shrink-0 shadow-[0_0_10px_rgba(16,185,129,0.3)]">
                <div className="w-2 h-2 bg-[#05070A] rounded-full"></div>
              </div>
              <div>
                <p className="text-[10px] font-mono font-bold text-gray-400 uppercase tracking-wider mb-0.5">Dropoff Destination</p>
                <p className="font-semibold text-[#F5F7FA] text-xs sm:text-sm">{ride.dropoff_location}</p>
              </div>
            </div>
          </div>

          {/* Dual Metric Cards */}
          <div className="grid grid-cols-2 gap-3.5 pt-5 mt-5 border-t border-[#1E293B]">
            <div className="bg-[#101820] p-4 rounded-xl border border-[#1E293B]">
              <div className="flex items-center gap-1.5 text-gray-400 mb-1">
                <Navigation size={13} className="text-[#38BDF8]" />
                <span className="text-[10px] font-mono uppercase">Distance</span>
              </div>
              <p className="text-xl font-bold text-[#F5F7FA]">{ride.distance_km} km</p>
            </div>
            <div className="bg-[#101820] p-4 rounded-xl border border-[#1E293B]">
              <div className="flex items-center gap-1.5 text-gray-400 mb-1">
                <span className="text-emerald-400 font-bold">₹</span>
                <span className="text-[10px] font-mono uppercase">Collect Fare</span>
              </div>
              <p className="text-xl font-bold text-emerald-400">₹{Number(ride.fare || 0).toFixed(2)}</p>
            </div>
          </div>
        </div>

        {/* Passenger Card */}
        {!isCancelled && (
          <div className="card p-5 flex items-center gap-4 bg-[#0A0F14] border border-[#1E293B] rounded-2xl shadow-lg">
            <div className="w-12 h-12 bg-[#101820] border border-[#1E293B] rounded-xl flex items-center justify-center shrink-0 text-[#38BDF8]">
              <User size={22} />
            </div>
            <div>
              <p className="text-[10px] font-mono font-bold text-gray-400 uppercase tracking-wider mb-0.5">Verified Passenger</p>
              <p className="font-bold text-[#F5F7FA] text-sm flex items-center gap-2">
                Passenger #{ride.passenger_id}
              </p>
            </div>
          </div>
        )}

        {/* Action Controls */}
        <div className="space-y-4">
          {ride.status === 'ACCEPTED' && (
            <button 
              onClick={handleStartRide} 
              disabled={actionLoading}
              className="btn btn-primary w-full h-14 text-sm font-bold uppercase tracking-wider rounded-xl flex items-center justify-center gap-3 shadow-[0_0_20px_rgba(56,189,248,0.3)]"
            >
              {actionLoading ? <Loader2 className="animate-spin w-5 h-5" /> : <><Play fill="currentColor" size={18} /> Start Ride Now</>}
            </button>
          )}

          {ride.status === 'STARTED' && (
            <div className="space-y-2">
              <div className="bg-emerald-500/10 text-emerald-400 p-3 rounded-xl border border-emerald-500/30 text-center text-xs font-mono flex items-center justify-center gap-2">
                <CheckCircle2 size={16} /> En route · Approaching Destination
              </div>
              <button 
                onClick={handleCompleteRide} 
                disabled={actionLoading}
                className="bg-emerald-500 hover:bg-emerald-400 text-bg-primary w-full h-14 text-sm font-bold uppercase tracking-wider rounded-xl flex items-center justify-center gap-3 shadow-[0_0_25px_rgba(16,185,129,0.35)] transition-all"
              >
                {actionLoading ? <Loader2 className="animate-spin w-5 h-5" /> : <><Check size={20} strokeWidth={3} /> Complete Ride & Collect</>}
              </button>
            </div>
          )}

          {ride.status === 'COMPLETED' && (
            <div className="bg-emerald-500/10 text-emerald-400 p-6 rounded-2xl border border-emerald-500/30 text-center font-bold text-base flex flex-col items-center justify-center gap-2 shadow-lg">
              <div className="w-14 h-14 bg-emerald-500 text-bg-primary rounded-full flex items-center justify-center shadow-[0_0_20px_rgba(16,185,129,0.4)] mb-2">
                <Check size={28} strokeWidth={3} />
              </div>
              Trip Completed Successfully
              <p className="text-xs font-mono font-normal text-gray-400">Total fare collected: ₹{Number(ride.fare || 0).toFixed(2)}</p>
            </div>
          )}
        </div>
      </div>
      
      {/* Right Column: Dark Command Map */}
      <div className="lg:col-span-7 min-h-[380px] lg:min-h-[540px] lg:sticky lg:top-4 self-start relative rounded-2xl overflow-hidden border border-[#1E293B] shadow-xl p-1 bg-[#0A0F14]">
        <Map markers={markers} />
      </div>
      
    </div>
  );
};

export default DriverRideDetails;
