import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useSocket } from '../../context/WebSocketContext';
import { getMyDriverProfile, updateDriverStatus, updateDriverLocation } from '../../services/driverService';
import {
  getAvailableRides,
  getDriverRides,
  acceptRide,
  rejectRide,
  startRide,
  completeRide,
} from '../../services/rideService';
import { getDriverBriefing } from '../../services/copilotService';
import Map from '../../components/Map';
import {
  Power,
  Navigation,
  MapPin,
  Loader2,
  Car,
  Clock,
  X,
  Check,
  Play,
  CheckCircle2,
  ChevronRight,
  AlertCircle,
  RefreshCw,
  User,
  Bot,
  Flame,
  Radio,
  Sparkles,
  Compass
} from 'lucide-react';
import toast from 'react-hot-toast';

const DriverDashboard = () => {
  const { user } = useAuth();
  const { isConnected: isSocketConnected, subscribe } = useSocket();
  const [profile, setProfile] = useState(null);
  const [briefing, setBriefing] = useState(null);
  const [activeRide, setActiveRide] = useState(null);
  const [availableRides, setAvailableRides] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState('');
  const [statusLoading, setStatusLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(null); // rideId
  const [currentLocation, setCurrentLocation] = useState(null);

  const fetchDashboardData = useCallback(async (isSilent = false) => {
    if (!isSilent) setFetchError('');
    try {
      const p = await getMyDriverProfile();
      setProfile(p);

      if (p.is_online) {
        // Fetch copilot briefing for hotspot intelligence
        getDriverBriefing().then(b => setBriefing(b)).catch(() => {});

        // 1. Fetch assigned rides for this driver to find active ride
        const myRidesResponse = await getDriverRides();
        const myRides = Array.isArray(myRidesResponse)
          ? myRidesResponse
          : myRidesResponse.items || [];
        
        const currentActive = myRides.find((r) =>
          ['REQUESTED', 'ACCEPTED', 'STARTED'].includes(r.status)
        );
        setActiveRide(currentActive || null);

        // 2. If no active ride is currently underway, check unassigned requests
        if (!currentActive) {
          const unassigned = await getAvailableRides();
          setAvailableRides(Array.isArray(unassigned) ? unassigned : []);
        } else {
          setAvailableRides([]);
        }
      } else {
        setActiveRide(null);
        setAvailableRides([]);
        setBriefing(null);
      }
    } catch (err) {
      console.error('Failed to load driver dashboard data:', err);
      if (!isSilent) {
        setFetchError('Unable to load current ride and dashboard data.');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();

    // Instant real-time updates via WebSocket event subscription
    const unsubscribe = subscribe((event) => {
      if (
        event.type === 'RIDE_ASSIGNED' ||
        event.type === 'RIDE_ACCEPTED' ||
        event.type === 'RIDE_REJECTED' ||
        event.type === 'RIDE_STARTED' ||
        event.type === 'RIDE_COMPLETED' ||
        event.type === 'RIDE_CANCELLED' ||
        event.type === 'NO_DRIVER_AVAILABLE'
      ) {
        fetchDashboardData(true);
      }
    });

    const interval = setInterval(() => {
      fetchDashboardData(true);
    }, 15000);

    return () => {
      unsubscribe();
      clearInterval(interval);
    };
  }, [fetchDashboardData, subscribe]);

  useEffect(() => {
    let locationInterval;
    if (profile?.is_online) {
      locationInterval = setInterval(() => {
        navigator.geolocation.getCurrentPosition(
          async (pos) => {
            const { latitude, longitude } = pos.coords;
            setCurrentLocation({ lat: latitude, lng: longitude });
            try {
              await updateDriverLocation(latitude, longitude);
            } catch (err) {
              console.error('Failed to update location', err);
            }
          },
          (err) => console.error('Geolocation error:', err),
          { enableHighAccuracy: true, timeout: 5000, maximumAge: 0 }
        );
      }, 15000);
    }
    return () => clearInterval(locationInterval);
  }, [profile?.is_online]);

  const toggleStatus = async () => {
    setStatusLoading(true);
    try {
      const newOnline = !profile.is_online;
      await updateDriverStatus(newOnline, newOnline);
      await fetchDashboardData();
      toast.success(newOnline ? 'Captain Status: ONLINE' : 'Captain Status: OFFLINE');
    } catch (err) {
      toast.error('Failed to update status');
    } finally {
      setStatusLoading(false);
    }
  };

  const handleAcceptRide = async (rideId) => {
    setActionLoading(rideId);
    try {
      await acceptRide(rideId);
      toast.success('Ride accepted! Route locked in.');
      await fetchDashboardData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to accept ride');
    } finally {
      setActionLoading(null);
    }
  };

  const handleRejectRide = async (rideId) => {
    setActionLoading(rideId);
    try {
      await rejectRide(rideId);
      toast.success('Ride declined. Relaying to next available driver.');
      setActiveRide(null);
      await fetchDashboardData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to reject ride');
    } finally {
      setActionLoading(null);
    }
  };

  const handleStartRide = async (rideId) => {
    setActionLoading(rideId);
    try {
      await startRide(rideId);
      toast.success('Ride started! Navigation active.');
      await fetchDashboardData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to start ride');
    } finally {
      setActionLoading(null);
    }
  };

  const handleCompleteRide = async (rideId) => {
    setActionLoading(rideId);
    try {
      await completeRide(rideId);
      toast.success('Ride completed! Earnings credited.');
      setActiveRide(null);
      await fetchDashboardData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to complete ride');
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex h-[80vh] items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-brand-400" />
      </div>
    );
  }

  const isOnline = profile?.is_online;

  // Build map markers
  const mapMarkers = [];
  if (currentLocation) {
    mapMarkers.push({
      lat: currentLocation.lat,
      lng: currentLocation.lng,
      type: 'driver',
      popup: 'Driver Position (You)',
    });
  }
  if (activeRide?.pickup_latitude && activeRide?.pickup_longitude) {
    mapMarkers.push({
      lat: activeRide.pickup_latitude,
      lng: activeRide.pickup_longitude,
      type: 'pickup',
      popup: `Pickup: ${activeRide.pickup_location}`,
    });
  }

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto min-h-full pb-20 animate-fade-in">
      {/* Top Status & Telemetry Banner */}
      <div
        className={`card-panel relative overflow-hidden transition-all duration-500 border rounded-2xl p-6 md:p-8 shadow-xl ${
          isOnline
            ? 'bg-gradient-to-r from-[#0E1A24] via-[#101820] to-[#0A0F14] border-[#38BDF8]/40 shadow-[0_0_25px_rgba(56,189,248,0.1)]'
            : 'bg-[#0A0F14] border-[#1E293B]'
        }`}
      >
        {isOnline && (
          <div className="absolute top-0 right-0 w-96 h-96 bg-[#38BDF8]/10 rounded-full blur-3xl pointer-events-none" />
        )}

        <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="flex items-center gap-5">
            <button
              onClick={toggleStatus}
              disabled={statusLoading}
              className={`relative flex items-center justify-center w-16 h-16 md:w-20 md:h-20 rounded-2xl shadow-xl transition-all active:scale-95 shrink-0 ${
                isOnline
                  ? 'bg-emerald-500/20 text-emerald-400 border-2 border-emerald-500/50 hover:bg-emerald-500/30 shadow-[0_0_20px_rgba(16,185,129,0.3)]'
                  : 'bg-[#101820] text-gray-500 border-2 border-[#1E293B] hover:text-gray-300'
              }`}
            >
              {statusLoading ? (
                <Loader2 className="w-8 h-8 animate-spin" />
              ) : (
                <Power strokeWidth={2.5} size={28} />
              )}
            </button>

            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <span
                  className={`w-2 h-2 rounded-full ${
                    isOnline ? 'bg-emerald-400 animate-ping' : 'bg-gray-600'
                  }`}
                />
                <span className="text-xs font-mono font-bold uppercase tracking-wider text-gray-400">
                  {isOnline ? 'Fleet Status: ONLINE & DISPATCH READY' : 'Fleet Status: OFFLINE'}
                </span>
              </div>
              <h1 className="text-2xl md:text-3xl font-bold text-[#F5F7FA] tracking-tight">
                {user?.name ? `Captain ${user.name}` : 'Driver Operations Deck'}
              </h1>
              <p className="text-xs sm:text-sm text-gray-400 mt-1 max-w-xl">
                {isOnline
                  ? 'Telemetry connected to RideNow dispatch engine. AI Copilot active.'
                  : 'Toggle switch to enter dispatch queue and receive nearby ride requests.'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 self-end md:self-auto">
            <Link
              to="/driver/copilot"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#101820] border border-[#1E293B] hover:border-[#38BDF8]/50 text-[#38BDF8] text-xs font-bold transition-all shadow-sm group"
            >
              <Bot className="w-4 h-4 text-[#38BDF8] group-hover:rotate-12 transition-transform" />
              <span>AI Copilot</span>
              <ChevronRight className="w-3.5 h-3.5 text-gray-400 group-hover:translate-x-0.5 transition-transform" />
            </Link>
          </div>
        </div>
      </div>

      {/* Error State with Retry Button */}
      {fetchError && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 text-red-400 rounded-xl flex items-center justify-between gap-3 text-sm">
          <div className="flex items-center gap-2">
            <AlertCircle size={18} className="shrink-0 text-red-400" />
            <span>{fetchError}</span>
          </div>
          <button
            onClick={() => fetchDashboardData(false)}
            className="flex items-center gap-1.5 px-3 py-1 bg-[#101820] border border-[#1E293B] text-white hover:bg-[#1E293B] rounded-lg text-xs font-medium transition-colors"
          >
            <RefreshCw size={12} /> Retry
          </button>
        </div>
      )}

      {/* Main Grid: Ride Operations (8 cols) + Map & Telemetry (4 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8">
        
        {/* Main Operations Column */}
        <div className="lg:col-span-8 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-[#F5F7FA] flex items-center gap-2">
              {activeRide ? 'Active Assignment' : 'Incoming Trip Queue'}
            </h2>
            {isOnline && (
              <span className="flex items-center gap-2 text-xs text-[#38BDF8] font-medium bg-[#101820] px-3 py-1 rounded-full border border-[#38BDF8]/30">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#38BDF8] opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-[#38BDF8]"></span>
                </span>
                {activeRide ? 'Trip In Progress' : 'Scanning Grid'}
              </span>
            )}
          </div>

          {!isOnline ? (
            <div className="card p-12 flex flex-col items-center justify-center text-center border-dashed border-2 border-[#1E293B] bg-[#0A0F14] rounded-2xl">
              <div className="w-14 h-14 rounded-2xl bg-[#101820] border border-[#1E293B] flex items-center justify-center text-gray-500 mb-4">
                <Power className="w-7 h-7 text-gray-500" />
              </div>
              <h3 className="text-lg font-bold text-[#F5F7FA]">Station is Offline</h3>
              <p className="text-gray-400 text-xs mt-1 max-w-sm">
                Activate the status button above to begin receiving passenger trip dispatches in real-time.
              </p>
            </div>
          ) : activeRide ? (
            /* ==========================================================
               CURRENT ACTIVE ASSIGNED RIDE CARD
               ========================================================== */
            <div className="card p-0 overflow-hidden border-2 border-[#38BDF8]/50 bg-[#0A0F14] rounded-2xl shadow-[0_0_30px_rgba(56,189,248,0.15)]">
              {/* Header banner */}
              <div className="bg-[#101820] p-6 border-b border-[#1E293B]">
                <div className="flex justify-between items-start">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider ${
                          activeRide.status === 'STARTED'
                            ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/40'
                            : 'bg-[#38BDF8]/15 text-[#38BDF8] border border-[#38BDF8]/40'
                        }`}
                      >
                        {activeRide.status === 'STARTED'
                          ? 'En Route to Destination'
                          : activeRide.status === 'ACCEPTED'
                          ? 'Assigned • Heading to Pickup'
                          : 'Assigned Ride'}
                      </span>
                      <span className="text-xs text-gray-400 font-mono">#{activeRide.id}</span>
                    </div>
                    <div className="text-3xl font-bold text-[#F5F7FA]">
                      {activeRide.fare ? `₹${Number(activeRide.fare).toFixed(2)}` : 'Calculated Fare'}
                    </div>
                    <div className="text-xs text-gray-400 mt-1 flex items-center gap-1.5">
                      <Navigation size={13} className="text-[#38BDF8]" />
                      <span>{activeRide.distance_km} km total journey</span>
                    </div>
                  </div>
                  <div className="w-12 h-12 bg-[#38BDF8]/15 text-[#38BDF8] border border-[#38BDF8]/30 rounded-2xl flex items-center justify-center shadow-[0_0_15px_rgba(56,189,248,0.2)]">
                    <Car size={22} />
                  </div>
                </div>
              </div>

              {/* Ride Route Details */}
              <div className="p-6 border-b border-[#1E293B] space-y-4">
                <div className="space-y-4 relative">
                  <div className="absolute left-2.5 top-3 bottom-3 w-0.5 bg-[#1E293B] z-0" />

                  <div className="flex items-start gap-4 relative z-10">
                    <div className="w-5 h-5 bg-[#101820] border-2 border-[#38BDF8] rounded-full mt-0.5 shrink-0 shadow-[0_0_8px_rgba(56,189,248,0.4)]" />
                    <div>
                      <p className="text-[10px] text-gray-400 font-bold uppercase tracking-wider mb-0.5">
                        Pickup Location
                      </p>
                      <p className="font-semibold text-[#F5F7FA] text-sm">{activeRide.pickup_location}</p>
                    </div>
                  </div>

                  <div className="flex items-start gap-4 relative z-10">
                    <div className="w-5 h-5 bg-[#10B981] border-2 border-[#10B981] rounded-full mt-0.5 shrink-0 shadow-[0_0_8px_rgba(16,185,129,0.4)]" />
                    <div>
                      <p className="text-[10px] text-gray-400 font-bold uppercase tracking-wider mb-0.5">
                        Dropoff Destination
                      </p>
                      <p className="font-semibold text-[#F5F7FA] text-sm">{activeRide.dropoff_location}</p>
                    </div>
                  </div>
                </div>

                {/* Passenger Info */}
                <div className="mt-4 pt-4 border-t border-[#1E293B] flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2 text-gray-300">
                    <User size={15} className="text-[#38BDF8]" />
                    <span>Passenger #{activeRide.passenger_id}</span>
                  </div>
                  <Link
                    to={`/driver/rides/${activeRide.id}`}
                    className="inline-flex items-center text-xs font-semibold text-[#38BDF8] hover:underline gap-1"
                  >
                    Trip Telemetry <ChevronRight size={14} />
                  </Link>
                </div>
              </div>

              {/* Action Buttons based on Status */}
              <div className="p-4 bg-[#101820]">
                {activeRide.status === 'ACCEPTED' && (
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      onClick={() => handleRejectRide(activeRide.id)}
                      disabled={actionLoading === activeRide.id}
                      className="px-4 py-3 rounded-xl border border-red-500/30 bg-red-500/10 text-red-400 hover:bg-red-500/20 text-xs font-bold uppercase tracking-wider transition-colors flex items-center justify-center gap-2"
                    >
                      {actionLoading === activeRide.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          <X size={16} /> Decline
                        </>
                      )}
                    </button>
                    <button
                      onClick={() => handleStartRide(activeRide.id)}
                      disabled={actionLoading === activeRide.id}
                      className="btn btn-primary py-3 rounded-xl text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(56,189,248,0.3)]"
                    >
                      {actionLoading === activeRide.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          <Play size={16} fill="currentColor" /> Start Trip Now
                        </>
                      )}
                    </button>
                  </div>
                )}

                {activeRide.status === 'STARTED' && (
                  <div className="space-y-2">
                    <div className="text-xs text-center text-gray-400 font-medium">
                      Trip in progress. Once you reach the destination, complete the ride.
                    </div>
                    <button
                      onClick={() => handleCompleteRide(activeRide.id)}
                      disabled={actionLoading === activeRide.id}
                      className="w-full py-3.5 px-4 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-bg-primary font-bold text-sm uppercase tracking-wider flex items-center justify-center gap-2 transition-all shadow-[0_0_25px_rgba(16,185,129,0.3)]"
                    >
                      {actionLoading === activeRide.id ? (
                        <Loader2 className="w-5 h-5 animate-spin" />
                      ) : (
                        <>
                          <CheckCircle2 size={18} /> Complete Trip & Collect Fare
                        </>
                      )}
                    </button>
                  </div>
                )}

                {activeRide.status === 'REQUESTED' && (
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      onClick={() => handleRejectRide(activeRide.id)}
                      disabled={actionLoading === activeRide.id}
                      className="px-4 py-3 rounded-xl border border-red-500/30 bg-red-500/10 text-red-400 hover:bg-red-500/20 text-xs font-bold uppercase tracking-wider transition-colors flex items-center justify-center gap-2"
                    >
                      {actionLoading === activeRide.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          <X size={16} /> Decline
                        </>
                      )}
                    </button>
                    <button
                      onClick={() => handleAcceptRide(activeRide.id)}
                      disabled={actionLoading === activeRide.id}
                      className="btn btn-primary py-3 rounded-xl text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(56,189,248,0.3)]"
                    >
                      {actionLoading === activeRide.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          <Check size={16} /> Accept Ride
                        </>
                      )}
                    </button>
                  </div>
                )}
              </div>
            </div>
          ) : availableRides.length > 0 ? (
            /* ==========================================================
               UNASSIGNED AVAILABLE RIDES LIST
               ========================================================== */
            <div className="space-y-4">
              {availableRides.map((ride) => (
                <div
                  key={ride.id}
                  className="card p-0 overflow-hidden border border-[#1E293B] hover:border-[#38BDF8]/50 transition-all rounded-2xl bg-[#0A0F14] shadow-lg"
                >
                  <div className="p-5 border-b border-[#1E293B]">
                    <div className="flex justify-between items-start mb-4">
                      <div>
                        <span className="inline-block px-2.5 py-0.5 bg-[#38BDF8]/10 text-[#38BDF8] border border-[#38BDF8]/20 text-xs font-bold rounded-full mb-2 uppercase tracking-wider">
                          Dispatch Alert
                        </span>
                        <div className="text-2xl font-bold text-[#F5F7FA]">
                          ₹{ride.fare ? Number(ride.fare).toFixed(2) : '--'}
                        </div>
                        <div className="text-xs text-gray-400 mt-0.5 flex items-center gap-1.5">
                          <Navigation size={12} className="text-[#38BDF8]" />
                          <span>{ride.distance_km} km</span>
                        </div>
                      </div>
                      <div className="w-10 h-10 rounded-xl bg-[#101820] border border-[#1E293B] flex items-center justify-center text-gray-400">
                        <Clock size={18} />
                      </div>
                    </div>

                    <div className="space-y-3 relative text-xs">
                      <div className="flex items-start gap-3">
                        <div className="w-2.5 h-2.5 rounded-full bg-[#38BDF8] mt-1 shrink-0" />
                        <div>
                          <p className="text-gray-400 font-medium text-[10px] uppercase">Pickup</p>
                          <p className="text-[#F5F7FA] font-semibold">{ride.pickup_location}</p>
                        </div>
                      </div>
                      <div className="flex items-start gap-3">
                        <div className="w-2.5 h-2.5 rounded-full bg-[#10B981] mt-1 shrink-0" />
                        <div>
                          <p className="text-gray-400 font-medium text-[10px] uppercase">Dropoff</p>
                          <p className="text-[#F5F7FA] font-semibold">{ride.dropoff_location}</p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 p-3.5 gap-3 bg-[#101820]">
                    <button
                      onClick={() => handleRejectRide(ride.id)}
                      disabled={actionLoading === ride.id}
                      className="px-4 py-2.5 rounded-xl border border-[#1E293B] text-gray-300 hover:bg-[#1E293B] text-xs font-medium flex items-center justify-center gap-1.5 transition-colors"
                    >
                      {actionLoading === ride.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          <X size={15} /> Decline
                        </>
                      )}
                    </button>
                    <button
                      onClick={() => handleAcceptRide(ride.id)}
                      disabled={actionLoading === ride.id}
                      className="btn btn-primary py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-1.5 shadow-[0_0_15px_rgba(56,189,248,0.25)]"
                    >
                      {actionLoading === ride.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          <Check size={15} /> Accept Ride
                        </>
                      )}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            /* ==========================================================
               LOOKING FOR RIDES RADAR STATE
               ========================================================== */
            <div className="card p-12 flex flex-col items-center justify-center text-center bg-[#0A0F14] border border-[#1E293B] rounded-2xl">
              <div className="relative mb-5">
                <div className="absolute inset-0 bg-[#38BDF8]/20 rounded-full animate-ping" />
                <div className="w-16 h-16 bg-[#101820] border border-[#38BDF8]/40 text-[#38BDF8] rounded-full flex items-center justify-center relative z-10 shadow-[0_0_20px_rgba(56,189,248,0.25)]">
                  <Navigation size={28} />
                </div>
              </div>
              <p className="text-[#F5F7FA] font-bold text-lg">Scanning Dispatch Grid...</p>
              <p className="text-gray-400 text-xs mt-1.5 max-w-sm">
                Positioned and waiting for passenger bookings. Keep GPS active.
              </p>
            </div>
          )}
        </div>

        {/* Sidebar: Map, Hotspots & Vehicle (4 cols) */}
        <div className="lg:col-span-4 space-y-6">
          {/* Dark Command Map */}
          <div className="card h-64 lg:h-72 p-1 relative overflow-hidden border border-[#1E293B] rounded-2xl bg-[#0A0F14] shadow-lg">
            <Map markers={mapMarkers} />
          </div>

          {/* Surge Hotspots Widget */}
          {briefing?.demand_zones && (
            <div className="card p-5 border border-[#1E293B] bg-[#0A0F14] rounded-2xl shadow-lg">
              <div className="flex items-center justify-between mb-3.5">
                <div className="flex items-center gap-2">
                  <Flame className="w-4 h-4 text-orange-400" />
                  <h3 className="text-xs font-bold text-[#F5F7FA] uppercase tracking-wider">Top Surge Sectors</h3>
                </div>
                <Link to="/driver/copilot" className="text-[11px] text-[#38BDF8] hover:underline font-medium">
                  Copilot View
                </Link>
              </div>
              <div className="space-y-2.5">
                {briefing.demand_zones.slice(0, 2).map((zone, idx) => (
                  <div key={idx} className="p-3 rounded-xl bg-[#101820] border border-[#1E293B] flex items-center justify-between text-xs">
                    <div>
                      <p className="font-semibold text-[#F5F7FA]">{zone.zone}</p>
                      <p className="text-[10px] text-gray-400 mt-0.5">ETA {zone.eta_mins}m • {zone.demand_level}</p>
                    </div>
                    <span className="text-xs font-bold text-orange-400 px-2.5 py-1 rounded-lg bg-orange-500/10 border border-orange-500/20">
                      {zone.surge_factor}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Vehicle Profile */}
          <div className="card p-5 border border-[#1E293B] bg-[#0A0F14] rounded-2xl shadow-lg">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4 flex items-center gap-2">
              <Car size={16} className="text-[#38BDF8]" /> Assigned Vehicle
            </h3>
            <div className="space-y-3 text-xs">
              <div className="flex justify-between items-center py-2 border-b border-[#1E293B]">
                <span className="text-gray-400">Class</span>
                <span className="font-semibold text-[#F5F7FA]">{profile?.vehicle_type || 'Standard'}</span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-[#1E293B]">
                <span className="text-gray-400">Model</span>
                <span className="font-semibold text-[#F5F7FA]">{profile?.vehicle_model || 'Sedan'}</span>
              </div>
              <div className="flex justify-between items-center py-2">
                <span className="text-gray-400">Plate Number</span>
                <span className="font-mono font-bold bg-[#101820] border border-[#1E293B] px-2.5 py-1 rounded-lg text-[#38BDF8] tracking-wider uppercase">
                  {profile?.vehicle_number || 'RN-CAB-001'}
                </span>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};

export default DriverDashboard;

