import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getRide, cancelRide } from '../../services/rideService';
import { processPayment } from '../../services/paymentService';
import { submitRating, getRideRating } from '../../services/ratingService';
import { useSocket } from '../../context/WebSocketContext';
import Map from '../../components/Map';
import ActiveRideSafetyPanel from '../../components/ActiveRideSafetyPanel';
import { Car, MapPin, Navigation, Clock, User, Phone, Star, ShieldCheck, X, Check, Loader2, Sparkles, Activity } from 'lucide-react';
import toast from 'react-hot-toast';
import { getErrorMessage } from '../../services/api';


const STATUS_STEPS = ['REQUESTED', 'ACCEPTED', 'STARTED', 'COMPLETED'];

const RideStatusProgress = ({ currentStatus }) => {
  let currentIndex = STATUS_STEPS.indexOf(currentStatus);
  if (currentStatus === 'CANCELLED') currentIndex = 0;

  return (
    <div className="relative mb-6 mt-3 px-2">
      <div className="absolute top-1/2 left-3 right-3 h-1 bg-border-default -translate-y-1/2 rounded-full z-0" />
      
      {/* Active Line */}
      {currentIndex >= 0 && currentStatus !== 'CANCELLED' && (
        <div 
          className="absolute top-1/2 left-3 h-1 bg-brand-400 -translate-y-1/2 rounded-full z-0 transition-all duration-500 ease-in-out shadow-glow"
          style={{ width: `${(currentIndex / (STATUS_STEPS.length - 1)) * 100}%` }}
        />
      )}

      <div className="flex justify-between relative z-10">
        {STATUS_STEPS.map((step, index) => {
          const isActive = index <= currentIndex && currentStatus !== 'CANCELLED';
          const isCurrent = index === currentIndex && currentStatus !== 'CANCELLED';
          
          return (
            <div key={step} className="flex flex-col items-center">
              <div className={`w-4 h-4 rounded-full flex items-center justify-center transition-all duration-300 ${
                isActive ? 'bg-brand-400 shadow-glow scale-110' : 'bg-bg-tertiary border border-border-default'
              }`}>
                {isActive && <div className="w-1.5 h-1.5 bg-bg-primary rounded-full" />}
              </div>
              <span className={`text-[10px] font-bold mt-2 uppercase tracking-wider transition-colors duration-300 ${
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

const RideDetails = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  
  const [ride, setRide] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [ratingLoading, setRatingLoading] = useState(false);
  const [rating, setRating] = useState(0);
  const [feedback, setFeedback] = useState('');
  const [existingRating, setExistingRating] = useState(null);

  const { subscribe, connectionState } = useSocket();
  const [driverLocation, setDriverLocation] = useState(null);
  const [lastLocationTime, setLastLocationTime] = useState(null);

  // Track whether the component is still mounted to ignore stale async results
  const isMountedRef = useRef(true);
  // Dedup guard: prevent showing the same error toast multiple times during polling/WS reconnect
  const errorShownRef = useRef(false);

  useEffect(() => {
    isMountedRef.current = true;
    errorShownRef.current = false;
    return () => {
      isMountedRef.current = false;
    };
  }, [id]);

  const fetchExistingRating = async (rideId) => {
    try {
      const data = await getRideRating(rideId);
      if (data && isMountedRef.current) {
        setExistingRating(data);
      }
    } catch {
      // rating may not exist yet — silently ignore
    }
  };

  const fetchRide = async () => {
    // Closure flag to detect if this specific call became stale
    let cancelled = false;

    try {
      const data = await getRide(id);

      // Ignore if component unmounted or this call was superseded
      if (!isMountedRef.current || cancelled) return;

      setRide(data);
      // Reset error dedup on successful fetch
      errorShownRef.current = false;

      if (data?.driver_info?.latitude && data?.driver_info?.longitude) {
        setDriverLocation({
          lat: data.driver_info.latitude,
          lng: data.driver_info.longitude,
          heading: 0,
        });
        if (data.driver_info.location_updated_at) {
          setLastLocationTime(new Date(data.driver_info.location_updated_at).getTime());
        }
      }
      if (data && data.status === 'COMPLETED') {
        fetchExistingRating(data.id);
      }
    } catch (err) {
      if (!isMountedRef.current || cancelled) return;

      const status = err?.response?.status;

      if (status === 401) {
        // The Axios interceptor in api.js already handles 401 (clears token, redirects to /login).
        // Do nothing here to avoid double-handling or duplicate navigation.
        return;
      }

      if (status === 404) {
        // Ride does not exist — navigate cleanly without a scary red error.
        // This is normal when a user browses to a stale or invalid ride URL.
        navigate('/rides', { replace: true });
        return;
      }

      if (status === 403) {
        // User is not a participant in this ride — navigate away cleanly.
        navigate('/rides', { replace: true });
        return;
      }

      // For 5xx server errors or network failures, show an informative error ONCE.
      // Do NOT repeat the toast on every polling cycle or WS-reconnect-triggered refetch.
      if (!errorShownRef.current) {
        errorShownRef.current = true;
        if (!err?.response) {
          toast.error('Network error — could not reach the server. Retrying…', { id: 'ride-fetch-err' });
        } else {
          toast.error(
            err?.response?.data?.detail || 'Could not load ride details. Please try again.',
            { id: 'ride-fetch-err' }
          );
        }
      }
    } finally {
      if (isMountedRef.current && !cancelled) {
        setLoading(false);
      }
    }

    // Return a cancel function (not actually needed for setTimeout callers, but kept for clarity)
    return () => { cancelled = true; };
  };

  const rideStatusRef = useRef(null);

  useEffect(() => {
    fetchRide();
  }, [id]);

  // Poll every 8s while ride is active — driven by ref to avoid stale closure loop
  useEffect(() => {
    rideStatusRef.current = ride?.status;
  }, [ride?.status]);

  useEffect(() => {
    const interval = setInterval(() => {
      const s = rideStatusRef.current;
      if (s && ['REQUESTED', 'ACCEPTED', 'STARTED'].includes(s)) {
        fetchRide();
      }
    }, 8000);
    return () => clearInterval(interval);
  }, [id]);

  // Subscribe to real-time driver telemetry updates
  useEffect(() => {
    const unsubscribe = subscribe((event) => {
      if (event.type === 'WS_RECONNECTED') {
        fetchRide();
      }
      if (
        (event.type === 'DRIVER_LOCATION_UPDATE' || event.type === 'driver_location') &&
        event
      ) {
        const lat = event.latitude ?? event.data?.latitude;
        const lng = event.longitude ?? event.data?.longitude;
        const driverId = event.driver_id ?? event.data?.driver_id;
        if (lat !== undefined && lng !== undefined) {
          if (!ride?.driver_id || driverId === ride.driver_id) {
            setDriverLocation({
              lat,
              lng,
              heading: event.heading ?? event.data?.heading ?? 0,
            });
            setLastLocationTime(event.timestamp ? new Date(event.timestamp).getTime() : Date.now());
          }
        }
      }
      if (event.type === 'ride_status_updated' && event.ride_id === Number(id)) {
        fetchRide();
      }
      // Refresh on any lifecycle event for this ride
      if (
        ['RIDE_ACCEPTED', 'RIDE_STARTED', 'RIDE_COMPLETED', 'RIDE_CANCELLED', 'DRIVER_MATCHED', 'DRIVER_REASSIGNED'].includes(event.type) &&
        event.ride_id === Number(id)
      ) {
        fetchRide();
      }
    });
    return () => {
      if (unsubscribe) unsubscribe();
    };
  }, [subscribe, ride?.driver_id, id]);

  const handleCancel = async () => {
    if (!window.confirm('Are you sure you want to cancel this ride?')) return;
    
    setActionLoading(true);
    try {
      await cancelRide(id);
      toast.success('Ride cancelled');
      await fetchRide();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to cancel ride');
    } finally {
      setActionLoading(false);
    }
  };

  const handlePayment = async () => {
    setActionLoading(true);
    try {
      await processPayment({
        ride_id: ride.id,
        payment_method: 'CASH',
      });
      toast.success('Payment recorded successfully');
      await fetchRide();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Payment settlement failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRating = async () => {
    if (rating === 0) {
      toast.error('Please select a star rating');
      return;
    }
    setRatingLoading(true);
    try {
      const result = await submitRating({
        ride_id: ride.id,
        rating,
        comment: feedback || undefined,
        feedback: feedback || undefined,
      });
      toast.success('Thank you for rating your captain!');
      setExistingRating(result);
      // Non-blocking reload — fetchRide handles its own errors internally
      fetchRide();
    } catch (err) {
      const status = err?.response?.status;
      if (status === 400) {
        // Duplicate rating or validation error — surface the exact backend message
        const detail = err?.response?.data?.detail;
        if (detail && detail.toLowerCase().includes('already been rated')) {
          toast.error('You have already rated this ride.');
          fetchRide(); // sync UI to show the existing rating
        } else {
          toast.error(detail || 'Rating could not be submitted. Please check your input.');
        }
      } else {
        toast.error(getErrorMessage(err, 'Rating submission failed. Please try again.'));
      }
    } finally {
      setRatingLoading(false);
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
    markers.push({
      id: 'pickup',
      lat: ride.pickup_latitude,
      lng: ride.pickup_longitude,
      type: 'pickup',
      popup: `Pickup: ${ride.pickup_location}`
    });
  }
  if (ride.dropoff_latitude && ride.dropoff_longitude) {
    markers.push({
      id: 'dropoff',
      lat: ride.dropoff_latitude,
      lng: ride.dropoff_longitude,
      type: 'dropoff',
      popup: `Dropoff: ${ride.dropoff_location}`
    });
  }
  if (driverLocation && ['ACCEPTED', 'STARTED'].includes(ride.status)) {
    markers.push({
      id: `driver-${ride.driver_id}`,
      lat: driverLocation.lat,
      lng: driverLocation.lng,
      type: 'driver',
      heading: driverLocation.heading || 0,
      popup: `Captain #${ride.driver_id}`
    });
  }
  
  const isCancelled = ride.status === 'CANCELLED';

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 max-w-6xl mx-auto min-h-[calc(100vh-140px)] animate-fade-in pb-20">
      
      {/* Left Column: Ride Telemetry & Status Cards */}
      <div className="lg:col-span-5 flex flex-col gap-6">
        
        {/* Status Header & Stepper Card */}
        <div className="card-panel p-6 border border-[#1E293B] bg-[#0A0F14] rounded-2xl shadow-xl overflow-hidden">
          <div className="flex justify-between items-start mb-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-mono uppercase bg-[#101820] text-[#38BDF8] border border-[#38BDF8]/30 px-2.5 py-0.5 rounded-full flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8] animate-ping" />
                  Live Corridor
                </span>
                <span className="text-xs text-gray-400 font-mono">#RN-{ride.id}</span>
              </div>
              <h1 className="text-2xl font-bold text-[#F5F7FA] mt-1">
                {isCancelled ? 'Trip Cancelled' : ride.status === 'COMPLETED' ? 'Trip Completed' : 'Active Telemetry'}
              </h1>
            </div>
            <div className="w-12 h-12 bg-[#38BDF8]/10 border border-[#38BDF8]/30 text-[#38BDF8] rounded-2xl flex items-center justify-center shadow-[0_0_15px_rgba(56,189,248,0.15)]">
              <Car size={22} />
            </div>
          </div>

          <RideStatusProgress currentStatus={ride.status} />
        </div>

        {/* Route Corridor Card */}
        <div className="card p-6 border border-[#1E293B] bg-[#0A0F14] rounded-2xl shadow-lg">
          <h2 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4 flex items-center gap-2">
            <Navigation size={14} className="text-[#38BDF8]" />
            Transit Route
          </h2>
          
          <div className="relative pl-1">
            <div className="absolute left-3.5 top-[22px] bottom-[22px] w-0.5 bg-[#1E293B] z-0" />
            
            <div className="relative z-10 flex gap-3.5 mb-5">
              <div className="w-7 h-7 bg-[#101820] border-2 border-[#38BDF8] rounded-full flex items-center justify-center shrink-0 shadow-[0_0_8px_rgba(56,189,248,0.4)]">
                <div className="w-2 h-2 bg-[#38BDF8] rounded-full" />
              </div>
              <div>
                <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Pickup Corridor</p>
                <p className="font-semibold text-[#F5F7FA] text-xs sm:text-sm mt-0.5">{ride.pickup_location}</p>
              </div>
            </div>

            <div className="relative z-10 flex gap-3.5">
              <div className="w-7 h-7 bg-[#10B981] border-2 border-[#10B981] rounded-full flex items-center justify-center shrink-0 shadow-[0_0_8px_rgba(16,185,129,0.4)]">
                <div className="w-2 h-2 bg-[#05070A] rounded-full" />
              </div>
              <div>
                <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Dropoff Destination</p>
                <p className="font-semibold text-[#F5F7FA] text-xs sm:text-sm mt-0.5">{ride.dropoff_location}</p>
              </div>
            </div>
          </div>

          {/* Metric Cards Grid */}
          <div className="grid grid-cols-2 gap-3.5 pt-5 mt-5 border-t border-[#1E293B]">
            <div className="bg-[#101820] p-4 rounded-xl border border-[#1E293B]">
              <div className="flex items-center gap-1.5 text-gray-400 text-xs mb-1">
                <Navigation size={13} className="text-[#38BDF8]" />
                <span className="font-mono uppercase text-[10px]">Distance</span>
              </div>
              <p className="text-xl font-bold text-[#F5F7FA]">{ride.distance_km} km</p>
            </div>
            <div className="bg-[#101820] p-4 rounded-xl border border-[#1E293B]">
              <div className="flex items-center gap-1.5 text-gray-400 text-xs mb-1">
                <span className="text-emerald-400 font-bold">₹</span>
                <span className="font-mono uppercase text-[10px]">Total Fare</span>
              </div>
              <p className="text-xl font-bold text-emerald-400">₹{Number(ride.fare || 0).toFixed(2)}</p>
            </div>
          </div>
        </div>

        {/* Real-time Safety Guard Panel (Active Trips) */}
        {['REQUESTED', 'ACCEPTED', 'STARTED'].includes(ride.status) && (
          <ActiveRideSafetyPanel ride={ride} onStatusChange={fetchRide} />
        )}

        {/* Assigned Driver Card */}

        {ride.driver_id && ride.status !== 'CANCELLED' && (
          <div className="card p-5 border border-[#1E293B] bg-[#0A0F14] rounded-2xl shadow-lg">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">Assigned Fleet Captain</h2>
              {/* Location Freshness Indicator */}
              {lastLocationTime ? (() => {
                const diffSec = Math.floor((Date.now() - lastLocationTime) / 1000);
                if (diffSec < 30) {
                  return (
                    <span className="flex items-center gap-1.5 text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      Live GPS
                    </span>
                  );
                } else if (diffSec < 120) {
                  return (
                    <span className="flex items-center gap-1.5 text-[10px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                      {diffSec}s ago
                    </span>
                  );
                } else {
                  return (
                    <span className="flex items-center gap-1.5 text-[10px] font-mono text-red-400 bg-red-500/10 px-2 py-0.5 rounded-full border border-red-500/20">
                      <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
                      Telemetry Stale
                    </span>
                  );
                }
              })() : null}
            </div>
            <div className="flex items-center gap-3.5">
              <div className="w-12 h-12 bg-[#38BDF8]/10 border border-[#38BDF8]/30 text-[#38BDF8] rounded-xl flex items-center justify-center shrink-0">
                <User size={22} />
              </div>
              <div className="flex-1">
                <p className="font-bold text-[#F5F7FA] text-sm flex items-center gap-1.5">
                  Captain #{ride.driver_id}
                  <ShieldCheck size={15} className="text-[#38BDF8]" />
                </p>
                <div className="flex items-center gap-1 text-amber-400 font-medium text-xs mt-0.5">
                  <Star size={12} fill="currentColor" /> Verified Driver
                </div>
              </div>
            </div>
            
            <div className="mt-4 p-3.5 bg-[#101820] border border-[#1E293B] rounded-xl flex items-center justify-between text-xs">
              <div>
                <p className="text-[10px] text-gray-400 uppercase font-mono">Vehicle Unit</p>
                <p className="font-semibold text-[#F5F7FA] mt-0.5">
                  {ride.driver_info?.vehicle_model || 'RideNow Sedan'}
                  {ride.driver_info?.vehicle_number && (
                    <span className="ml-2 font-mono text-[11px] text-gray-400 bg-bg-secondary px-1.5 py-0.5 rounded border border-border-default">
                      {ride.driver_info.vehicle_number}
                    </span>
                  )}
                </p>
              </div>
              <div className="text-right">
                <p className="text-[10px] text-gray-400 uppercase font-mono">Class</p>
                <span className="font-mono text-xs text-[#38BDF8] font-bold uppercase">
                  {ride.driver_info?.vehicle_type || 'Standard'}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Action Controls / Cancel / Settle / Rating */}
        <div className="space-y-4">
          {['REQUESTED', 'ACCEPTED'].includes(ride.status) && (
            <button 
              onClick={handleCancel} 
              disabled={actionLoading}
              className="w-full py-3.5 rounded-xl border border-red-500/30 bg-red-500/10 text-red-400 hover:bg-red-500/20 font-bold text-xs uppercase tracking-wider transition-colors flex items-center justify-center gap-2"
            >
              {actionLoading ? <Loader2 className="animate-spin w-4 h-4" /> : 'Cancel Ride Request'}
            </button>
          )}

          {ride.status === 'COMPLETED' && (
            <div className="space-y-4 animate-fade-in">
              {/* Payment Settlement Card */}
              <div className="card p-5 border border-emerald-500/30 bg-gradient-to-b from-[#0A0F14] to-emerald-950/20 rounded-2xl shadow-lg">
                <h3 className="font-bold text-[#F5F7FA] text-sm mb-1 text-center">Settlement Status</h3>
                <div className="flex justify-between items-center py-3 border-b border-[#1E293B] mb-3.5 text-xs">
                  <span className="text-gray-400">Total Due:</span>
                  <span className="text-2xl font-bold text-[#F5F7FA]">₹{Number(ride.fare || 0).toFixed(2)}</span>
                </div>
                <button 
                  onClick={handlePayment} 
                  disabled={actionLoading}
                  className="btn btn-primary w-full py-3 text-xs font-bold uppercase tracking-wider rounded-xl shadow-[0_0_20px_rgba(56,189,248,0.3)]"
                >
                  {actionLoading ? <Loader2 className="animate-spin w-4 h-4 mx-auto" /> : 'Settle Fare (Cash / UPI)'}
                </button>
              </div>

              {/* Driver Rating Card */}
              {existingRating ? (
                <div className="card p-5 text-center bg-[#0A0F14] border border-[#1E293B] rounded-2xl shadow-lg">
                  <div className="flex items-center justify-center gap-1.5 text-[#38BDF8] text-xs font-bold uppercase tracking-wider mb-2">
                    <Check size={14} /> Trip Rated
                  </div>
                  <h3 className="font-bold text-[#F5F7FA] text-sm mb-2">Your Rating</h3>
                  <div className="flex justify-center gap-1.5 mb-2">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <Star 
                        key={star} 
                        size={22} 
                        className={star <= existingRating.rating ? "text-amber-400" : "text-gray-600"} 
                        fill={star <= existingRating.rating ? "currentColor" : "none"} 
                      />
                    ))}
                  </div>
                  <p className="text-[#F5F7FA] font-mono font-bold text-sm">{existingRating.rating} / 5</p>
                  {existingRating.comment && (
                    <p className="text-xs text-gray-400 mt-2.5 italic bg-[#101820] p-3 rounded-xl border border-[#1E293B]">
                      "{existingRating.comment}"
                    </p>
                  )}
                </div>
              ) : (
                <div className="card p-5 text-center bg-[#0A0F14] border border-[#1E293B] rounded-2xl shadow-lg">
                  <h3 className="font-bold text-[#F5F7FA] text-sm mb-1">Rate Your Trip</h3>
                  <p className="text-xs text-gray-400 mb-3.5">Help maintain the RideNow service quality standard</p>
                  <div className="flex justify-center gap-2 mb-3.5">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <button 
                        key={star} 
                        type="button" 
                        onClick={() => setRating(star)} 
                        className={`transition-all ${rating >= star ? 'text-amber-400 scale-110' : 'text-gray-600 hover:text-amber-400/50'}`}
                      >
                        <Star size={28} fill={rating >= star ? 'currentColor' : 'none'} strokeWidth={1.5} />
                      </button>
                    ))}
                  </div>
                  <textarea
                    rows={2}
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                    placeholder="Add optional driver feedback or trip notes..."
                    className="w-full bg-[#101820] border border-[#1E293B] rounded-xl p-3 text-xs text-white placeholder-gray-500 mb-3.5 focus:outline-none focus:border-[#38BDF8]/50 resize-none"
                  />
                  <button 
                    onClick={handleRating} 
                    disabled={ratingLoading || rating === 0} 
                    className="btn btn-primary w-full py-3 rounded-xl text-xs font-bold uppercase tracking-wider transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {ratingLoading ? <Loader2 className="animate-spin w-4 h-4 mx-auto" /> : 'Submit Driver Rating'}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      
      {/* Right Column: Dark Map Telemetry */}
      <div className="lg:col-span-7 min-h-[380px] lg:min-h-[540px] lg:sticky lg:top-4 relative rounded-2xl overflow-hidden card p-1 border border-[#1E293B] self-start shadow-xl">
        <Map markers={markers} animateDrivers={true} />
      </div>
      
    </div>
  );
};

export default RideDetails;

