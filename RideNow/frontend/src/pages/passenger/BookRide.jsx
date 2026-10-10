import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { requestRide, getFareEstimate } from '../../services/rideService';
import Map from '../../components/Map';
import {
  MapPin, Navigation, Loader2, ArrowRight, CheckCircle2,
  Car, Sparkles, ShieldCheck, IndianRupee, RotateCcw,
} from 'lucide-react';
import toast from 'react-hot-toast';

// step: 'input' | 'estimate' | 'booking' | 'matched'
const BookRide = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const [pickup, setPickup] = useState('');
  const [dropoff, setDropoff] = useState('');

  const [step, setStep] = useState('input');
  const [estimate, setEstimate] = useState(null);  // fare estimate data
  const [rideResult, setRideResult] = useState(null); // created ride data

  // Pre-fill from query params (e.g. from AI suggestion)
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const p = params.get('pickup');
    const d = params.get('dropoff');
    if (p) setPickup(p);
    if (d) setDropoff(d);
  }, [location]);

  // STEP 1 → STEP 2: calculate fare estimate (no ride created)
  const handleCalculate = async (e) => {
    e.preventDefault();
    if (!pickup.trim() || !dropoff.trim()) {
      toast.error('Please provide both pickup and destination');
      return;
    }
    setStep('loading_estimate');
    try {
      const data = await getFareEstimate(pickup.trim(), dropoff.trim());
      setEstimate(data);
      setStep('estimate');
      toast.success('Route calculated!');
    } catch (err) {
      setStep('input');
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        toast.error(detail);
      } else {
        toast.error('Could not resolve location. Please try a more specific address.');
      }
    }
  };

  // STEP 2 → STEP 3: confirm booking, create ride
  const handleConfirmBook = async () => {
    if (!estimate) return;
    setStep('booking');
    try {
      const ride = await requestRide({
        pickup_location: pickup.trim(),
        dropoff_location: dropoff.trim(),
        pickup_latitude: estimate.pickup_latitude,
        pickup_longitude: estimate.pickup_longitude,
      });
      setRideResult(ride);
      setStep('matched');
      toast.success(
        ride.driver_id
          ? '🚗 Driver assigned! Redirecting...'
          : '✅ Ride requested! Finding driver...',
      );
      setTimeout(() => {
        navigate(`/rides/${ride.id}`);
      }, 1800);
    } catch (err) {
      setStep('estimate'); // Go back to estimate step on error
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        toast.error(detail);
      } else {
        toast.error('Failed to book ride. Please try again.');
      }
    }
  };

  const handleReset = () => {
    setStep('input');
    setEstimate(null);
    setRideResult(null);
  };

  // Map markers
  const mapMarkers = [];
  const coordSource = estimate || rideResult;
  if (coordSource?.pickup_latitude && coordSource?.pickup_longitude) {
    mapMarkers.push({
      lat: coordSource.pickup_latitude,
      lng: coordSource.pickup_longitude,
      type: 'pickup',
      popup: `Pickup: ${pickup}`,
    });
  }
  if (coordSource?.dropoff_latitude && coordSource?.dropoff_longitude) {
    mapMarkers.push({
      lat: coordSource.dropoff_latitude,
      lng: coordSource.dropoff_longitude,
      type: 'dropoff',
      popup: `Dropoff: ${dropoff}`,
    });
  }

  const isLoading = step === 'loading_estimate' || step === 'booking';

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 lg:h-[calc(100vh-140px)] min-h-[540px] max-w-6xl mx-auto animate-fade-in pb-12 lg:pb-0">

      {/* Left Column: Booking Terminal */}
      <div className="lg:col-span-5 flex flex-col h-full">
        <div className="card-panel flex flex-col h-full p-0 overflow-hidden border-border-default">

          {/* Header */}
          <div className="p-6 border-b border-border-default bg-bg-secondary z-10 relative">
            <div className="inline-flex items-center gap-2 px-2.5 py-0.5 rounded-full bg-brand-500/10 border border-brand-500/20 text-brand-400 text-[11px] font-semibold uppercase tracking-wider mb-2">
              <Sparkles className="w-3 h-3" />
              {step === 'input' || step === 'loading_estimate' ? 'OSRM Georouting' :
               step === 'estimate' ? 'Fare Confirmed' :
               step === 'booking' ? 'Dispatching...' : 'Driver Found'}
            </div>
            <h1 className="text-xl font-bold text-white">
              {step === 'input' || step === 'loading_estimate'
                ? 'Request Mobility Transport'
                : step === 'estimate'
                ? 'Verify Trip Telemetry'
                : step === 'booking'
                ? 'Securing Driver...'
                : 'Ride Confirmed!'}
            </h1>
            <p className="text-xs text-gray-400 mt-0.5">
              {step === 'input' || step === 'loading_estimate'
                ? 'Input origin and destination coordinates to lock in fare'
                : step === 'estimate'
                ? 'Review algorithmic route estimate before dispatch'
                : step === 'booking'
                ? 'Matching the nearest available driver unit...'
                : 'Redirecting to your live ride tracker...'}
            </p>
          </div>

          {/* Body */}
          <div className="p-6 flex-1 overflow-y-auto bg-bg-primary/50">
            {(step === 'input' || step === 'loading_estimate') && (
              <form id="bookForm" onSubmit={handleCalculate} className="space-y-6">
                <div className="relative">
                  <div className="absolute left-5 top-[30px] bottom-[30px] w-0.5 bg-border-default z-0" />
                  <div className="relative z-10 space-y-5">
                    <div className="flex items-start gap-4">
                      <div className="w-10 h-10 rounded-xl bg-bg-tertiary border border-border-default flex items-center justify-center text-brand-400 shrink-0">
                        <MapPin size={18} />
                      </div>
                      <div className="flex-1">
                        <label className="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1.5 ml-1">
                          Pickup Location
                        </label>
                        <input
                          type="text"
                          className="input-field text-sm"
                          placeholder="Current location or pickup address..."
                          value={pickup}
                          onChange={(e) => setPickup(e.target.value)}
                          required
                        />
                      </div>
                    </div>

                    <div className="flex items-start gap-4">
                      <div className="w-10 h-10 rounded-xl bg-brand-500/20 border border-brand-500/30 text-brand-400 flex items-center justify-center shrink-0">
                        <Navigation size={18} />
                      </div>
                      <div className="flex-1">
                        <label className="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1.5 ml-1">
                          Dropoff Destination
                        </label>
                        <input
                          type="text"
                          className="input-field text-sm"
                          placeholder="Where are you traveling to?"
                          value={dropoff}
                          onChange={(e) => setDropoff(e.target.value)}
                          required
                        />
                      </div>
                    </div>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-bg-tertiary/40 border border-border-default flex items-center gap-3 text-xs text-gray-400">
                  <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span>Transparent upfront pricing. No hidden congestion surcharge.</span>
                </div>
              </form>
            )}

            {step === 'estimate' && estimate && (
              <div className="space-y-5 animate-fade-in">
                {/* Fare card */}
                <div className="bg-bg-tertiary/60 p-5 rounded-2xl border border-border-default">
                  <div className="flex justify-between items-center mb-4">
                    <div className="flex items-center gap-2">
                      <Car className="text-brand-400" size={22} />
                      <span className="font-bold text-white text-base">RideNow Fleet Standard</span>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-white flex items-center gap-1">
                        <IndianRupee size={18} />
                        {estimate.estimated_fare?.toFixed(2)}
                      </div>
                      <div className="text-xs text-gray-400">{estimate.distance_km} km • ₹12/km</div>
                    </div>
                  </div>

                  <div className="border-t border-border-default pt-4 space-y-3">
                    <div className="flex gap-3 text-xs">
                      <div className="w-2 h-2 mt-1.5 bg-brand-400 rounded-full shrink-0" />
                      <div>
                        <p className="text-[11px] text-gray-400 uppercase font-semibold">Pickup</p>
                        <p className="font-medium text-white">{pickup}</p>
                      </div>
                    </div>
                    <div className="flex gap-3 text-xs">
                      <div className="w-2 h-2 mt-1.5 bg-emerald-400 rounded-full shrink-0" />
                      <div>
                        <p className="text-[11px] text-gray-400 uppercase font-semibold">Destination</p>
                        <p className="font-medium text-white">{dropoff}</p>
                      </div>
                    </div>
                  </div>

                  {/* Fare breakdown */}
                  <div className="mt-4 pt-4 border-t border-border-default">
                    <div className="flex justify-between text-xs text-gray-400 mb-1">
                      <span>Base fare</span>
                      <span>₹{estimate.base_fare?.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-xs text-gray-400">
                      <span>Distance ({estimate.distance_km} km × ₹{estimate.per_km_rate})</span>
                      <span>₹{((estimate.distance_km || 0) * (estimate.per_km_rate || 12)).toFixed(2)}</span>
                    </div>
                  </div>
                </div>

                <button
                  onClick={handleReset}
                  className="text-xs text-brand-400 font-medium hover:underline w-full text-center flex items-center justify-center gap-1"
                >
                  <RotateCcw size={12} />
                  Edit Route Parameters
                </button>
              </div>
            )}

            {step === 'booking' && (
              <div className="flex flex-col items-center justify-center py-12 gap-4 animate-fade-in">
                <div className="w-16 h-16 rounded-full bg-brand-500/20 border border-brand-500/40 text-brand-400 flex items-center justify-center shadow-glow relative">
                  <div className="absolute inset-0 bg-brand-500/30 rounded-full animate-ping" />
                  <Car size={26} />
                </div>
                <p className="text-sm text-gray-300 text-center">Broadcasting to fleet grid...<br />Matching nearest available driver.</p>
              </div>
            )}

            {step === 'matched' && (
              <div className="flex flex-col items-center justify-center py-12 gap-4 animate-fade-in">
                <div className="w-16 h-16 rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 flex items-center justify-center">
                  <CheckCircle2 size={30} />
                </div>
                <p className="text-sm text-gray-300 text-center">
                  {rideResult?.driver_id ? '🚗 Driver assigned!' : '✅ Ride booked!'}<br />
                  Redirecting to your live tracker...
                </p>
              </div>
            )}
          </div>

          {/* Footer CTA */}
          <div className="p-5 bg-bg-secondary border-t border-border-default z-10">
            {(step === 'input' || step === 'loading_estimate') && (
              <button
                form="bookForm"
                type="submit"
                className="btn-primary w-full h-12 text-sm font-bold shadow-glow"
                disabled={isLoading || !pickup || !dropoff}
              >
                {step === 'loading_estimate'
                  ? <Loader2 className="animate-spin w-5 h-5 mx-auto" />
                  : 'Calculate Route & Fare'}
              </button>
            )}

            {step === 'estimate' && (
              <button
                onClick={handleConfirmBook}
                className="btn-primary w-full h-12 text-sm font-bold shadow-glow flex items-center justify-center gap-2"
              >
                <ArrowRight className="w-4 h-4" />
                Confirm & Book for ₹{estimate?.estimated_fare?.toFixed(2)}
              </button>
            )}

            {(step === 'booking' || step === 'matched') && (
              <button disabled className="w-full h-12 text-sm font-bold rounded-xl bg-bg-tertiary text-gray-500 flex items-center justify-center gap-2">
                <Loader2 className="animate-spin w-4 h-4" />
                Processing...
              </button>
            )}
          </div>

        </div>
      </div>

      {/* Right Column: Dark Command Map */}
      <div className="lg:col-span-7 h-64 lg:h-full relative rounded-2xl overflow-hidden card-panel p-1 border-border-default">
        <Map markers={mapMarkers} />

        {/* Loading overlay while dispatching */}
        {step === 'booking' && (
          <div className="absolute inset-0 bg-bg-primary/80 backdrop-blur-md z-20 flex flex-col items-center justify-center animate-fade-in">
            <div className="w-16 h-16 rounded-full bg-brand-500/20 border border-brand-500/40 text-brand-400 flex items-center justify-center shadow-glow mb-4 relative">
              <div className="absolute inset-0 bg-brand-500/30 rounded-full animate-ping" />
              <Car size={26} />
            </div>
            <h3 className="text-lg font-bold text-white">Broadcasting to Fleet Grid</h3>
            <p className="text-xs text-gray-400 mt-1">Matching closest available driver unit...</p>
          </div>
        )}
      </div>

    </div>
  );
};

export default BookRide;
