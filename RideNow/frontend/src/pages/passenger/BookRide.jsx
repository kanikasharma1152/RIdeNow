import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { requestRide, matchDriver } from '../../services/rideService';
import Map from '../../components/Map';
import { MapPin, Navigation, Loader2, ArrowRight, CheckCircle2, Car, Sparkles, ShieldCheck } from 'lucide-react';
import toast from 'react-hot-toast';

const BookRide = () => {
  const navigate = useNavigate();
  const location = useLocation();
  
  const [pickup, setPickup] = useState('');
  const [dropoff, setDropoff] = useState('');
  
  const [loading, setLoading] = useState(false);
  const [rideResult, setRideResult] = useState(null);
  const [matchingStatus, setMatchingStatus] = useState('idle'); // idle, finding, matched
  
  // Try to grab pre-filled data from URL parameters
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const p = params.get('pickup');
    const d = params.get('dropoff');
    if (p) setPickup(p);
    if (d) setDropoff(d);
  }, [location]);

  const handleBook = async (e) => {
    e.preventDefault();
    if (!pickup || !dropoff) {
      toast.error("Please provide both pickup and destination");
      return;
    }
    
    setLoading(true);
    try {
      const response = await requestRide({
        pickup_location: pickup,
        dropoff_location: dropoff,
      });
      setRideResult(response);
      toast.success("Ride calculated successfully");
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to calculate ride');
    } finally {
      setLoading(false);
    }
  };

  const handleMatchDriver = async () => {
    if (!rideResult) return;
    setMatchingStatus('finding');
    
    try {
      const matched = await matchDriver(rideResult.id);
      setMatchingStatus('matched');
      toast.success("Driver locked in!");
      setTimeout(() => {
        navigate(`/rides/${matched.id}`);
      }, 1500);
    } catch (err) {
      setMatchingStatus('idle');
      toast.error(err.response?.data?.detail || 'Failed to match driver');
    }
  };

  const mapMarkers = [];
  if (rideResult?.pickup_latitude && rideResult?.pickup_longitude) {
    mapMarkers.push({
      lat: rideResult.pickup_latitude,
      lng: rideResult.pickup_longitude,
      type: 'pickup',
      popup: `Pickup: ${rideResult.pickup_location}`
    });
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 lg:h-[calc(100vh-140px)] min-h-[540px] max-w-6xl mx-auto animate-fade-in pb-12 lg:pb-0">
      
      {/* Left Column: Booking Terminal */}
      <div className="lg:col-span-5 flex flex-col h-full">
        <div className="card-panel flex flex-col h-full p-0 overflow-hidden border-border-default">
          
          <div className="p-6 border-b border-border-default bg-bg-secondary z-10 relative">
            <div className="inline-flex items-center gap-2 px-2.5 py-0.5 rounded-full bg-brand-500/10 border border-brand-500/20 text-brand-400 text-[11px] font-semibold uppercase tracking-wider mb-2">
              <Sparkles className="w-3 h-3" />
              OSRM Georouting
            </div>
            <h1 className="text-xl font-bold text-white">
              {!rideResult ? 'Request Mobility Transport' : 'Verify Trip Telemetry'}
            </h1>
            <p className="text-xs text-gray-400 mt-0.5">
              {!rideResult ? 'Input origin and destination coordinates to lock in fare' : 'Review algorithmic route estimate before dispatch'}
            </p>
          </div>

          <div className="p-6 flex-1 overflow-y-auto bg-bg-primary/50">
            {!rideResult ? (
              // Step 1: Input Form
              <form id="bookForm" onSubmit={handleBook} className="space-y-6">
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
            ) : (
              // Step 2: Ride Summary
              <div className="space-y-6 animate-fade-in">
                <div className="bg-bg-tertiary/60 p-5 rounded-2xl border border-border-default">
                  <div className="flex justify-between items-center mb-4">
                    <div className="flex items-center gap-2">
                      <Car className="text-brand-400" size={22} />
                      <span className="font-bold text-white text-base">RideNow Fleet Standard</span>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-white">₹{rideResult.fare || '0.00'}</div>
                      <div className="text-xs text-gray-400">{rideResult.distance_km} km distance</div>
                    </div>
                  </div>

                  <div className="border-t border-border-default pt-4 space-y-3">
                    <div className="flex gap-3 text-xs">
                      <div className="w-2 h-2 mt-1.5 bg-brand-400 rounded-full shrink-0" />
                      <div>
                        <p className="text-[11px] text-gray-400 uppercase font-semibold">Pickup</p>
                        <p className="font-medium text-white">{rideResult.pickup_location}</p>
                      </div>
                    </div>
                    <div className="flex gap-3 text-xs">
                      <div className="w-2 h-2 mt-1.5 bg-emerald-400 rounded-full shrink-0" />
                      <div>
                        <p className="text-[11px] text-gray-400 uppercase font-semibold">Destination</p>
                        <p className="font-medium text-white">{rideResult.dropoff_location}</p>
                      </div>
                    </div>
                  </div>
                </div>

                <button 
                  onClick={() => {
                    setRideResult(null);
                    setMatchingStatus('idle');
                  }}
                  className="text-xs text-brand-400 font-medium hover:underline w-full text-center"
                >
                  ← Edit Route Parameters
                </button>
              </div>
            )}
          </div>

          <div className="p-5 bg-bg-secondary border-t border-border-default z-10">
            {!rideResult ? (
              <button 
                form="bookForm"
                type="submit" 
                className="btn-primary w-full h-12 text-sm font-bold shadow-glow" 
                disabled={loading || !pickup || !dropoff}
              >
                {loading ? <Loader2 className="animate-spin w-5 h-5 mx-auto" /> : 'Calculate Route & Fare'}
              </button>
            ) : (
              <button 
                onClick={handleMatchDriver} 
                className={`w-full h-12 text-sm font-bold rounded-xl transition-all flex items-center justify-center ${
                  matchingStatus === 'matched' 
                    ? 'bg-emerald-500 text-bg-primary' 
                    : 'btn-primary shadow-glow'
                }`}
                disabled={matchingStatus !== 'idle'}
              >
                {matchingStatus === 'finding' ? (
                  <><Loader2 className="animate-spin mr-2 w-4 h-4" /> Dispatching nearest captain...</>
                ) : matchingStatus === 'matched' ? (
                  <><CheckCircle2 className="mr-2 w-4 h-4" /> Driver Assigned!</>
                ) : (
                  <><ArrowRight className="mr-2 w-4 h-4" /> Confirm & Dispatch Driver</>
                )}
              </button>
            )}
          </div>
          
        </div>
      </div>
      
      {/* Right Column: Dark Command Map */}
      <div className="lg:col-span-7 h-64 lg:h-full relative rounded-2xl overflow-hidden card-panel p-1 border-border-default">
        <Map markers={mapMarkers} />
        
        {/* Loading overlay for map when finding driver */}
        {matchingStatus === 'finding' && (
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

