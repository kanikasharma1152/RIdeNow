import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useSocket } from '../../context/WebSocketContext';
import { getPassengerRides } from '../../services/rideService';
import Map from '../../components/Map';
import {
  MapPin,
  Navigation,
  Clock,
  ChevronRight,
  Search,
  Sparkles,
  Car,
  ShieldCheck,
  Zap,
  ArrowRight,
  Activity,
  Bot
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const PassengerDashboard = () => {
  const { user } = useAuth();
  const { subscribe } = useSocket();
  const navigate = useNavigate();
  
  const [recentRides, setRecentRides] = useState([]);
  const [activeRide, setActiveRide] = useState(null);
  const [loading, setLoading] = useState(true);
  
  const [pickup, setPickup] = useState('');
  const [dropoff, setDropoff] = useState('');

  const fetchDashboardData = async () => {
    try {
      const response = await getPassengerRides(); 
      const rides = Array.isArray(response) ? response : (response.items || []);
      
      // Look for active trip in REQUESTED, ACCEPTED, or STARTED state
      const active = rides.find((r) => ['REQUESTED', 'ACCEPTED', 'STARTED'].includes(r.status));
      setActiveRide(active || null);

      // Past recent rides
      const past = rides.filter((r) => ['COMPLETED', 'CANCELLED'].includes(r.status));
      setRecentRides(past.slice(0, 3));
    } catch (err) {
      console.error("Error fetching passenger dashboard data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();

    // Subscribe to live ride events
    const unsubscribe = subscribe((event) => {
      if (
        event.type === 'DRIVER_MATCHED' ||
        event.type === 'DRIVER_REASSIGNED' ||
        event.type === 'RIDE_ACCEPTED' ||
        event.type === 'RIDE_STARTED' ||
        event.type === 'RIDE_COMPLETED' ||
        event.type === 'RIDE_CANCELLED' ||
        event.type === 'NO_DRIVER_AVAILABLE'
      ) {
        fetchDashboardData();
      }
    });

    return () => unsubscribe();
  }, [subscribe]);

  const handleSearch = (e) => {
    e.preventDefault();
    if (pickup && dropoff) {
      navigate(`/book-ride?pickup=${encodeURIComponent(pickup)}&dropoff=${encodeURIComponent(dropoff)}`);
    } else {
      navigate('/book-ride');
    }
  };

  // Build map markers for preview
  const mapMarkers = [];
  if (activeRide?.pickup_latitude && activeRide?.pickup_longitude) {
    mapMarkers.push({
      lat: activeRide.pickup_latitude,
      lng: activeRide.pickup_longitude,
      type: 'pickup',
      popup: `Pickup: ${activeRide.pickup_location}`,
    });
  }

  return (
    <div className="flex flex-col gap-6 lg:gap-8 max-w-6xl mx-auto pb-16 animate-fade-in">
      {/* Hero Welcome & Mobility Command Header */}
      <div className="card-panel relative overflow-hidden bg-gradient-to-r from-[#0D141B] via-[#101820] to-[#0A0F14] border border-[#1E293B] p-6 md:p-8 rounded-2xl shadow-xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-[#38BDF8]/5 rounded-full blur-3xl pointer-events-none" />
        
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#101820] border border-[#38BDF8]/30 text-[#38BDF8] text-xs font-semibold uppercase tracking-wider mb-3">
              <span className="w-2 h-2 rounded-full bg-[#38BDF8] animate-ping" />
              Mobility Core Active
            </div>
            <h1 className="text-2xl md:text-3xl font-bold text-[#F5F7FA] tracking-tight">
              Good {new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 18 ? 'afternoon' : 'evening'}, {user?.name?.split(' ')[0]} 👋
            </h1>
            <p className="text-sm text-gray-400 mt-1 max-w-xl">
              Where would you like to travel today? RideNow AI dispatch is standing by with live route optimization.
            </p>
          </div>

          {/* Top Quick Actions */}
          <div className="flex flex-wrap items-center gap-3">
            <Link
              to="/assistant"
              className="flex items-center gap-2.5 px-4 py-2.5 bg-[#101820] border border-[#1E293B] hover:border-[#38BDF8]/60 rounded-xl text-xs font-bold text-gray-200 hover:text-[#38BDF8] transition-all shadow-sm group"
            >
              <Sparkles size={16} className="text-[#38BDF8] group-hover:rotate-12 transition-transform" />
              <span>Nova AI</span>
            </Link>
            <Link
              to="/book-ride"
              className="btn btn-primary px-5 py-2.5 text-xs font-bold uppercase tracking-wider rounded-xl flex items-center gap-2 shadow-[0_0_20px_rgba(56,189,248,0.25)]"
            >
              <Navigation size={15} />
              <span>Book Ride</span>
            </Link>
          </div>
        </div>
      </div>

      {/* ACTIVE RIDE CARD (If Active Trip in Progress) */}
      {activeRide && (
        <div className="card-interactive p-6 rounded-2xl bg-gradient-to-r from-[#0E1A24] via-[#101820] to-[#0A0F14] border-2 border-[#38BDF8]/50 shadow-[0_0_30px_rgba(56,189,248,0.15)] flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-[#38BDF8]/15 border border-[#38BDF8]/40 text-[#38BDF8] flex items-center justify-center shrink-0 shadow-[0_0_15px_rgba(56,189,248,0.2)]">
              <Car size={24} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider px-2.5 py-0.5 bg-[#38BDF8] text-[#05070A] rounded-md font-bold">
                  {activeRide.status}
                </span>
                <span className="text-xs font-mono text-gray-400">Ride #{activeRide.id}</span>
                <span className="flex items-center gap-1 text-[11px] text-[#38BDF8] font-semibold">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8] animate-pulse" /> Live Tracking
                </span>
              </div>
              <h3 className="text-lg font-bold text-[#F5F7FA] mt-1.5">{activeRide.dropoff_location}</h3>
              <p className="text-xs text-gray-400 mt-0.5">
                Pickup: {activeRide.pickup_location} · {activeRide.distance_km} km
              </p>
            </div>
          </div>

          <div className="flex items-center gap-5">
            {activeRide.fare && (
              <div className="text-right">
                <div className="text-2xl font-bold text-[#F5F7FA]">₹{Number(activeRide.fare).toFixed(2)}</div>
                <span className="text-[10px] text-gray-400 uppercase tracking-widest font-mono">Trip Fare</span>
              </div>
            )}
            <Link
              to={`/rides/${activeRide.id}`}
              className="btn btn-primary px-6 py-3 text-xs font-bold uppercase tracking-wider rounded-xl flex items-center gap-2 shadow-[0_0_20px_rgba(56,189,248,0.3)]"
            >
              <span>Track Ride Live</span>
              <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      )}

      {/* Main Operations Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8">
        
        {/* Left Column: Instant Booking & Quick Actions */}
        <div className="lg:col-span-5 flex flex-col gap-6">
          
          {/* Instant Booking Card */}
          <div className="card p-6 border border-[#1E293B] bg-[#0A0F14] rounded-2xl shadow-lg relative overflow-hidden">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-[#F5F7FA] flex items-center gap-2">
                <Navigation size={18} className="text-[#38BDF8]" />
                Request a Ride
              </h2>
              <span className="text-[10px] font-mono text-[#38BDF8] bg-[#38BDF8]/10 px-2 py-0.5 rounded border border-[#38BDF8]/20">
                OSRM Fast Engine
              </span>
            </div>
            
            <form onSubmit={handleSearch} className="space-y-4">
              <div className="relative">
                <div className="absolute left-4 top-1/2 -translate-y-1/2 flex flex-col items-center gap-1 z-10">
                  <div className="w-2.5 h-2.5 rounded-full bg-[#38BDF8] shadow-[0_0_8px_#38BDF8]"></div>
                  <div className="w-0.5 h-7 bg-[#1E293B]"></div>
                  <div className="w-2.5 h-2.5 rounded-sm bg-[#10B981]"></div>
                </div>
                
                <div className="space-y-3 pl-8">
                  <div>
                    <label className="text-[10px] uppercase font-bold text-gray-400 tracking-wider block mb-1">Pickup Point</label>
                    <input
                      type="text"
                      value={pickup}
                      onChange={(e) => setPickup(e.target.value)}
                      placeholder="Current location or pickup address..."
                      className="input-field text-xs sm:text-sm bg-[#101820] border-[#1E293B]"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] uppercase font-bold text-gray-400 tracking-wider block mb-1">Destination</label>
                    <input
                      type="text"
                      value={dropoff}
                      onChange={(e) => setDropoff(e.target.value)}
                      placeholder="Where to? (Destination address)"
                      className="input-field text-xs sm:text-sm bg-[#101820] border-[#1E293B]"
                    />
                  </div>
                </div>
              </div>

              <button 
                type="submit" 
                className="btn btn-primary w-full h-12 text-xs font-bold uppercase tracking-wider mt-2 shadow-[0_0_20px_rgba(56,189,248,0.25)] rounded-xl"
              >
                Estimate Fare & Route
              </button>
            </form>
          </div>

          {/* Quick Action Navigation Tiles */}
          <div className="grid grid-cols-2 gap-3.5">
            <Link 
              to="/book-ride" 
              className="card-interactive p-4 rounded-xl flex flex-col items-center justify-center text-center gap-2 bg-[#0A0F14] border border-[#1E293B] group"
            >
              <div className="w-10 h-10 rounded-xl bg-[#101820] text-[#38BDF8] border border-[#1E293B] flex items-center justify-center group-hover:bg-[#38BDF8] group-hover:text-[#05070A] transition-colors shadow-sm">
                <Navigation size={18} />
              </div>
              <span className="text-xs font-semibold text-[#F5F7FA]">Book Ride</span>
              <span className="text-[10px] text-gray-500">Instant dispatch</span>
            </Link>
            
            <Link 
              to="/rides" 
              className="card-interactive p-4 rounded-xl flex flex-col items-center justify-center text-center gap-2 bg-[#0A0F14] border border-[#1E293B] group"
            >
              <div className="w-10 h-10 rounded-xl bg-[#101820] text-gray-400 border border-[#1E293B] flex items-center justify-center group-hover:border-[#38BDF8]/50 group-hover:text-[#38BDF8] transition-colors shadow-sm">
                <Clock size={18} />
              </div>
              <span className="text-xs font-semibold text-[#F5F7FA]">Ride History</span>
              <span className="text-[10px] text-gray-500">Past journeys</span>
            </Link>

            <Link 
              to="/payments" 
              className="card-interactive p-4 rounded-xl flex flex-col items-center justify-center text-center gap-2 bg-[#0A0F14] border border-[#1E293B] group"
            >
              <div className="w-10 h-10 rounded-xl bg-[#101820] text-emerald-400 border border-[#1E293B] flex items-center justify-center group-hover:border-emerald-500/50 transition-colors shadow-sm">
                <span className="font-bold text-base">₹</span>
              </div>
              <span className="text-xs font-semibold text-[#F5F7FA]">Payments</span>
              <span className="text-[10px] text-gray-500">Fares & ledger</span>
            </Link>

            <Link 
              to="/assistant" 
              className="card-interactive p-4 rounded-xl flex flex-col items-center justify-center text-center gap-2 bg-[#0A0F14] border border-[#1E293B] group"
            >
              <div className="w-10 h-10 rounded-xl bg-[#101820] text-[#38BDF8] border border-[#1E293B] flex items-center justify-center group-hover:bg-[#38BDF8]/20 transition-colors shadow-sm">
                <Bot size={18} />
              </div>
              <span className="text-xs font-semibold text-[#F5F7FA]">Nova Assistant</span>
              <span className="text-[10px] text-gray-500">AI Mobility Copilot</span>
            </Link>
          </div>

          {/* AI Prompts Card */}
          <div className="card p-5 border border-[#1E293B] bg-[#101820] rounded-2xl">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles size={16} className="text-[#38BDF8]" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#F5F7FA]">Ask Nova Mobility AI</h3>
            </div>
            <div className="space-y-2">
              {[
                "Estimate fare for a 12 km trip",
                "What is the platform cancellation policy?",
                "Where is my active driver?"
              ].map((prompt, i) => (
                <Link
                  key={i}
                  to={`/assistant?q=${encodeURIComponent(prompt)}`}
                  className="flex items-center justify-between p-2.5 rounded-xl bg-[#0A0F14] border border-[#1E293B] hover:border-[#38BDF8]/50 text-xs text-gray-300 hover:text-[#38BDF8] transition-all group"
                >
                  <span className="truncate mr-2">“{prompt}”</span>
                  <ChevronRight size={14} className="text-gray-500 group-hover:text-[#38BDF8] group-hover:translate-x-0.5 transition-transform shrink-0" />
                </Link>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Map Preview & Recent Trips Cards */}
        <div className="lg:col-span-7 flex flex-col gap-6">
          
          {/* Map Preview Card */}
          <div 
            className="card p-1.5 h-64 lg:h-[300px] relative overflow-hidden group cursor-pointer bg-[#0A0F14] rounded-2xl border border-[#1E293B]" 
            onClick={() => navigate('/book-ride')}
          >
            <Map markers={mapMarkers} interactive={false} />
            <div className="absolute bottom-4 right-4 z-20">
              <span className="bg-[#101820]/90 backdrop-blur-md border border-[#1E293B] px-3.5 py-1.5 rounded-full text-xs font-semibold flex items-center gap-2 text-[#38BDF8] shadow-lg">
                <Search size={14} /> Full Route Map
              </span>
            </div>
          </div>

          {/* Recent Rides Module */}
          <div className="card p-6 border border-[#1E293B] bg-[#0A0F14] rounded-2xl">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-base font-bold text-[#F5F7FA]">Recent Journeys</h3>
                <p className="text-xs text-gray-400">Your latest transit records and telemetry</p>
              </div>
              <Link to="/rides" className="text-xs font-semibold text-[#38BDF8] hover:underline flex items-center gap-1">
                View All <ChevronRight size={14} />
              </Link>
            </div>
            
            {loading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="animate-pulse flex gap-4 p-4 bg-[#101820] rounded-xl border border-[#1E293B]">
                    <div className="w-10 h-10 bg-gray-800 rounded-lg shrink-0"></div>
                    <div className="flex-1 space-y-2 py-1">
                      <div className="h-4 bg-gray-800 rounded w-3/4"></div>
                      <div className="h-3 bg-gray-800 rounded w-1/4"></div>
                    </div>
                  </div>
                ))}
              </div>
            ) : recentRides.length > 0 ? (
              <div className="space-y-3">
                {recentRides.map((ride) => (
                  <Link 
                    to={`/rides/${ride.id}`} 
                    key={ride.id}
                    className="card-interactive flex items-center justify-between p-4 rounded-xl bg-[#101820] border border-[#1E293B] hover:border-[#38BDF8]/40 transition-all group"
                  >
                    <div className="flex items-center gap-3.5 overflow-hidden">
                      <div className="w-10 h-10 rounded-xl bg-[#0A0F14] border border-[#1E293B] text-gray-400 flex items-center justify-center shrink-0 group-hover:text-[#38BDF8] group-hover:border-[#38BDF8]/30 transition-colors">
                        <MapPin size={18} />
                      </div>
                      <div className="truncate">
                        <p className="text-sm font-semibold text-[#F5F7FA] truncate">
                          {ride.dropoff_location}
                        </p>
                        <p className="text-xs text-gray-400 mt-0.5">
                          {formatDistanceToNow(new Date(ride.created_at), { addSuffix: true })} · {ride.distance_km} km
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 shrink-0">
                      {ride.fare && (
                        <span className="text-sm font-mono font-bold text-[#F5F7FA] px-2.5 py-1 bg-[#0A0F14] rounded-lg border border-[#1E293B]">
                          ₹{Number(ride.fare).toFixed(2)}
                        </span>
                      )}
                      <ChevronRight size={16} className="text-gray-500 group-hover:text-[#38BDF8] transition-colors" />
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="text-center py-10">
                <div className="w-12 h-12 rounded-xl bg-[#101820] border border-[#1E293B] flex items-center justify-center mx-auto mb-3 text-gray-500">
                  <Navigation size={22} />
                </div>
                <p className="text-gray-300 text-sm font-semibold">No past journeys on record yet</p>
                <p className="text-gray-500 text-xs mt-1">Ready for your first ride? Request one using the booking box.</p>
              </div>
            )}
          </div>
          
        </div>
      </div>
    </div>
  );
};

export default PassengerDashboard;
