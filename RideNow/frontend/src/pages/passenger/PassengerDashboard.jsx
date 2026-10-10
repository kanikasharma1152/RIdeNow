/**
 * RideNow — AI-First Passenger Home Screen
 * ==========================================
 * The primary interaction paradigm: "Where do you want to go?"
 *
 * Layout:
 *   - Time-aware greeting
 *   - AI Command Bar (text + voice + camera)
 *   - Active ride card (pinned when riding)
 *   - Live map (full width, real data)
 *   - Smart destination suggestions
 *   - Recent journeys
 *
 * All data comes from real API. No fake/mock data.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
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
  Sparkles,
  Car,
  ArrowRight,
  Mic,
  Camera,
  Send,
  Loader2,
  Bot,
  Star,
  ShieldCheck,
  CreditCard,
  X,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import toast from 'react-hot-toast';
import { analyzeLocationImage } from '../../services/visionService';
import { mobilityService } from '../../services/mobilityService';

// Greeting based on local time
function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  if (h < 21) return 'Good evening';
  return 'Good night';
}

// Smart destination chips — shown from recent rides
function buildSuggestions(recentRides) {
  const seen = new Set();
  const chips = [];
  for (const ride of recentRides) {
    const loc = ride.dropoff_location;
    if (loc && !seen.has(loc)) {
      seen.add(loc);
      chips.push(loc);
    }
    if (chips.length >= 3) break;
  }
  return chips;
}

export default function PassengerDashboard() {
  const { user } = useAuth();
  const { subscribe } = useSocket();
  const navigate = useNavigate();

  const [recentRides, setRecentRides]   = useState([]);
  const [activeRide, setActiveRide]     = useState(null);
  const [mobilitySummary, setMobilitySummary] = useState(null);
  const [loading, setLoading]           = useState(true);
  const [userLocation, setUserLocation] = useState(null);

  // AI Command Bar state
  const [query, setQuery]         = useState('');
  const [isListening, setIsListening] = useState(false);
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [uploadingImage, setUploadingImage] = useState(false);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);

  // ── Data fetching ──────────────────────────────────────────────────────
  const fetchData = useCallback(async () => {
    try {
      const response = await getPassengerRides();
      const rides = Array.isArray(response) ? response : (response.items || []);

      const active = rides.find(r => ['REQUESTED', 'ACCEPTED', 'STARTED'].includes(r.status));
      setActiveRide(active || null);

      const past = rides.filter(r => ['COMPLETED', 'CANCELLED'].includes(r.status));
      setRecentRides(past.slice(0, 5));

      // Fetch mobility intelligence summary
      try {
        const mobRes = await mobilityService.getMyMobilitySummary();
        if (mobRes?.success && mobRes.data) {
          setMobilitySummary(mobRes.data);
        }
      } catch (e) {
        // Silently ignore if not available
      }
    } catch (err) {
      console.error('Dashboard data error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();

    // Geolocation for passenger marker
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
        () => {} // silent fail
      );
    }

    // Live ride events
    const unsub = subscribe((event) => {
      const RIDE_EVENTS = [
        'DRIVER_MATCHED', 'DRIVER_REASSIGNED', 'RIDE_ACCEPTED',
        'RIDE_STARTED', 'RIDE_COMPLETED', 'RIDE_CANCELLED', 'NO_DRIVER_AVAILABLE',
      ];
      if (RIDE_EVENTS.includes(event.type)) fetchData();
    });

    return () => unsub();
  }, [subscribe, fetchData]);

  // ── Command bar handlers ───────────────────────────────────────────────
  const handleImageSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      toast.error('Image size must be under 10MB');
      return;
    }
    setImageFile(file);
    const reader = new FileReader();
    reader.onload = () => setImagePreview(reader.result);
    reader.readAsDataURL(file);
    toast.success('Location photo attached');
  };

  const removeImage = () => {
    setImageFile(null);
    setImagePreview(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleCommandSubmit = async (e) => {
    e?.preventDefault();
    const q = query.trim();

    // If image attached, process with vision service
    if (imageFile) {
      setUploadingImage(true);
      try {
        const visionRes = await analyzeLocationImage(
          imageFile,
          q,
          userLocation ? { latitude: userLocation.lat, longitude: userLocation.lng } : null
        );
        removeImage();
        const contextualQuery = q ? `${q} (Location from photo: ${visionRes.message})` : `Location from photo: ${visionRes.message}`;
        navigate(`/assistant?q=${encodeURIComponent(contextualQuery)}`);
      } catch (err) {
        toast.error('Failed to process image');
      } finally {
        setUploadingImage(false);
      }
      return;
    }

    if (!q) return;

    // Check if it's a destination (short phrase → book ride)
    // vs a question (contains ?, "how", "what", "why" → AI assistant)
    const aiKeywords = /\?|how|what|why|policy|cancel|help|fare estimate|earnings|where is|book|chhod|jana hai|jaana hai/i;
    if (aiKeywords.test(q)) {
      navigate(`/assistant?q=${encodeURIComponent(q)}`);
    } else {
      // Treat as destination
      navigate(`/book-ride?dropoff=${encodeURIComponent(q)}`);
    }
  };

  const handleSuggestionClick = (destination) => {
    navigate(`/book-ride?dropoff=${encodeURIComponent(destination)}`);
  };

  const handleVoice = () => {
    if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
      toast('Voice input is not supported in this browser. Try Chrome.', { icon: '🎙️' });
      return;
    }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new SR();
    rec.lang = 'en-IN'; // Indian English
    rec.interimResults = false;
    setIsListening(true);

    rec.onresult = (e) => {
      const transcript = e.results[0][0].transcript;
      setQuery(transcript);
      setIsListening(false);
    };
    rec.onerror = () => { setIsListening(false); };
    rec.onend   = () => { setIsListening(false); };
    rec.start();
  };

  const handleCamera = () => {
    fileInputRef.current?.click();
  };

  // ── Map markers ────────────────────────────────────────────────────────
  const mapMarkers = [];

  if (userLocation) {
    mapMarkers.push({
      lat: userLocation.lat,
      lng: userLocation.lng,
      type: 'passenger',
      popup: 'Your location',
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

  const suggestions = buildSuggestions(recentRides);
  const mapCenter = userLocation
    ? [userLocation.lat, userLocation.lng]
    : [12.9716, 77.5946];

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto pb-20 animate-[page-enter_300ms_ease-out]">

      {/* ── Active Ride Banner ──────────────────────────────────────── */}
      {activeRide && (
        <div className="relative overflow-hidden rounded-2xl border-2 border-[#38BDF8]/50 bg-gradient-to-r from-[#0E1A24] via-[#101820] to-[#0A0F14] shadow-[0_0_30px_rgba(56,189,248,0.12)]">
          <div className="absolute top-0 right-0 w-64 h-64 bg-[#38BDF8]/5 rounded-full blur-3xl pointer-events-none" />
          <div className="relative z-10 flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5">
            <div className="flex items-center gap-4">
              <div className="w-11 h-11 rounded-xl bg-[#38BDF8]/15 border border-[#38BDF8]/40 text-[#38BDF8] flex items-center justify-center shrink-0 shadow-[0_0_15px_rgba(56,189,248,0.2)]">
                <Car size={22} />
              </div>
              <div>
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 bg-[#38BDF8] text-[#05070A] rounded">
                    {activeRide.status}
                  </span>
                  <span className="flex items-center gap-1 text-[11px] text-[#38BDF8] font-semibold">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8] animate-pulse" />
                    Live
                  </span>
                </div>
                <p className="text-sm font-bold text-[#F5F7FA]">{activeRide.dropoff_location}</p>
                <p className="text-[11px] text-gray-400">From: {activeRide.pickup_location} · {activeRide.distance_km} km</p>
              </div>
            </div>
            <Link
              to={`/rides/${activeRide.id}`}
              className="btn btn-primary text-xs font-bold uppercase tracking-wider rounded-xl px-5 py-2.5 shadow-[0_0_20px_rgba(56,189,248,0.3)] whitespace-nowrap flex items-center gap-2"
            >
              Track Live <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      )}

      {/* ── Hero: AI Command ────────────────────────────────────────── */}
      <div className="relative overflow-hidden rounded-3xl bg-[#080E15] border border-[#1A2535]">
        {/* Background glow */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-[#38BDF8]/[0.04] rounded-full blur-3xl" />
        </div>

        <div className="relative z-10 px-6 pt-8 pb-6 md:px-10 md:pt-10 md:pb-8">
          {/* Greeting */}
          <div className="flex items-center gap-2 mb-1">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#101820] border border-[#38BDF8]/25 text-[#38BDF8] text-[10px] font-semibold tracking-widest uppercase">
              <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8] animate-pulse" />
              AI Ready
            </div>
          </div>

          <h1 className="text-2xl md:text-4xl font-bold text-[#F5F7FA] mt-3 mb-1" style={{ letterSpacing: '-0.02em' }}>
            {getGreeting()}, {user?.name?.split(' ')[0] || 'there'}.
          </h1>
          <p className="text-base md:text-lg text-gray-400 mb-7">
            Where do you want to go?
          </p>

          {/* AI Command Bar */}
          <form onSubmit={handleCommandSubmit}>
            {/* Hidden file input */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleImageSelect}
              accept="image/*"
              className="hidden"
            />

            {/* Attached image thumbnail preview */}
            {imagePreview && (
              <div className="flex items-center gap-2 mb-2 p-2 rounded-xl bg-[#101820] border border-[#38BDF8]/40 w-fit">
                <img
                  src={imagePreview}
                  alt="Location preview"
                  className="w-10 h-10 object-cover rounded-lg border border-[#1E293B]"
                />
                <div className="text-xs">
                  <p className="font-semibold text-gray-200">Location photo attached</p>
                  <p className="text-[10px] text-gray-400">Will analyze landmarks upon sending</p>
                </div>
                <button
                  type="button"
                  onClick={removeImage}
                  className="p-1 text-gray-400 hover:text-red-400 transition-colors ml-1"
                  aria-label="Remove image"
                >
                  <X size={14} />
                </button>
              </div>
            )}

            <div className="flex items-center gap-2 bg-[#0D141B] border border-[#1E293B] rounded-2xl px-4 py-3 focus-within:border-[#38BDF8]/50 focus-within:shadow-[0_0_0_3px_rgba(56,189,248,0.08)] transition-all">
              <MapPin size={18} className="text-[#38BDF8] shrink-0" />

              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Destination, or ask Nova anything…"
                className="flex-1 bg-transparent text-[#F5F7FA] placeholder-gray-500 text-sm md:text-base focus:outline-none"
                aria-label="Destination or AI query"
              />

              {query && (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  className="text-gray-500 hover:text-gray-300 transition-colors"
                  aria-label="Clear"
                >
                  <X size={15} />
                </button>
              )}

              {/* Voice input */}
              <button
                type="button"
                onClick={handleVoice}
                className={`p-2 rounded-xl transition-all ${
                  isListening
                    ? 'bg-[#38BDF8]/20 text-[#38BDF8] shadow-[0_0_12px_rgba(56,189,248,0.3)]'
                    : 'text-gray-500 hover:text-[#38BDF8] hover:bg-[#38BDF8]/10'
                }`}
                aria-label="Voice input"
              >
                {isListening ? (
                  <span className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8] animate-ping" />
                    <Mic size={16} />
                  </span>
                ) : (
                  <Mic size={16} />
                )}
              </button>

              {/* Camera / image input */}
              <button
                type="button"
                onClick={handleCamera}
                className="p-2 rounded-xl text-gray-500 hover:text-[#38BDF8] hover:bg-[#38BDF8]/10 transition-all"
                aria-label="Image location input"
              >
                <Camera size={16} />
              </button>

              {/* Submit */}
              <button
                type="submit"
                disabled={!query.trim()}
                className="p-2 rounded-xl bg-[#38BDF8] text-[#05070A] disabled:opacity-30 hover:bg-[#5CC8FF] transition-all shadow-sm"
                aria-label="Go"
              >
                <Send size={15} />
              </button>
            </div>
          </form>

          {/* Smart destination chips */}
          {suggestions.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-4">
              {suggestions.map((dest, i) => (
                <button
                  key={i}
                  onClick={() => handleSuggestionClick(dest)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#101820] border border-[#1E293B] text-xs text-gray-300 hover:text-[#38BDF8] hover:border-[#38BDF8]/40 transition-all"
                >
                  <Clock size={11} className="text-gray-500 shrink-0" />
                  <span className="truncate max-w-[140px]">{dest}</span>
                </button>
              ))}
              <Link
                to="/assistant"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#38BDF8]/10 border border-[#38BDF8]/25 text-xs text-[#38BDF8] hover:bg-[#38BDF8]/20 transition-all"
              >
                <Sparkles size={11} />
                Ask Nova AI
              </Link>
              <button
                onClick={() => {
                  setQuery('Plan a trip to ');
                  if (inputRef.current) inputRef.current.focus();
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#101820] border border-[#1E293B] text-xs text-sky-400 hover:border-[#38BDF8]/40 transition-all"
              >
                <Clock size={11} /> Plan a Trip
              </button>
              <button
                onClick={() => {
                  setQuery('How much did I spend this month?');
                  if (inputRef.current) inputRef.current.focus();
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#101820] border border-[#1E293B] text-xs text-amber-400 hover:border-amber-400/40 transition-all"
              >
                <CreditCard size={11} /> My Spend
              </button>
            </div>
          )}

          {suggestions.length === 0 && (
            <div className="flex flex-wrap gap-2 mt-4">
              {[
                { label: 'Book a ride', icon: <Navigation size={11} />, to: '/book-ride' },
                { label: 'Plan a trip', icon: <Clock size={11} />, to: '/assistant?q=Plan a trip to Airport' },
                { label: 'My ride spend', icon: <CreditCard size={11} />, to: '/assistant?q=How much did I spend this month?' },
                { label: 'Smart pickup points', icon: <MapPin size={11} />, to: '/assistant?q=Best pickup points near me' },
                { label: 'Cancellation policy', icon: <ShieldCheck size={11} />, to: '/assistant?q=What is the cancellation policy?' },
              ].map((chip, i) => (
                <Link
                  key={i}
                  to={chip.to}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#101820] border border-[#1E293B] text-xs text-gray-300 hover:text-[#38BDF8] hover:border-[#38BDF8]/40 transition-all"
                >
                  <span className="text-gray-500">{chip.icon}</span>
                  {chip.label}
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Predictive Mobility Intelligence Card ────────────────────────── */}
      {mobilitySummary && (mobilitySummary.lifetime_stats?.completed_trips > 0 || mobilitySummary.recent_30_days?.completed_trips > 0) && (
        <div className="relative overflow-hidden rounded-2xl border border-[#38BDF8]/20 bg-gradient-to-r from-[#0C1924]/90 via-[#0A131C] to-[#070D12] p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-lg animate-[fade-in_200ms_ease-out]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[#38BDF8]/15 border border-[#38BDF8]/30 flex items-center justify-center text-[#38BDF8] shrink-0">
              <Sparkles size={18} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#38BDF8] bg-[#38BDF8]/10 px-2 py-0.5 rounded">
                  AI Mobility Insights
                </span>
                <span className="text-xs text-gray-400">
                  {mobilitySummary.preferred_travel_window || 'Regular'} Traveler
                </span>
              </div>
              <p className="text-xs text-gray-200 mt-0.5">
                {mobilitySummary.top_destinations?.length > 0 ? (
                  <>Frequent route: <span className="font-semibold text-white">{mobilitySummary.top_destinations[0].destination}</span> ({mobilitySummary.top_destinations[0].trips} trips) · ₹{mobilitySummary.lifetime_stats?.total_spend_inr} spent</>
                ) : (
                  <>{mobilitySummary.lifetime_stats?.completed_trips} completed trips · Lifetime spend: ₹{mobilitySummary.lifetime_stats?.total_spend_inr}</>
                )}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => {
                const dest = mobilitySummary.top_destinations?.[0]?.destination || 'Railway Station';
                setQuery(`Plan my trip to ${dest}`);
                if (inputRef.current) inputRef.current.focus();
              }}
              className="px-3 py-1.5 rounded-lg bg-[#38BDF8]/10 hover:bg-[#38BDF8]/20 border border-[#38BDF8]/30 text-xs font-semibold text-[#38BDF8] transition-colors flex items-center gap-1.5"
            >
              <Clock size={12} /> Plan Commute
            </button>
            <button
              onClick={() => {
                setQuery('How much did I spend this month?');
                if (inputRef.current) inputRef.current.focus();
              }}
              className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-semibold text-gray-300 transition-colors"
            >
              View Spend
            </button>
          </div>
        </div>
      )}

      {/* ── Main Grid: Map + Sidebar ─────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* Map — 7 columns, full height */}
        <div className="lg:col-span-7 h-[320px] lg:h-[420px] relative group cursor-pointer rounded-2xl overflow-hidden border border-[#1E293B] shadow-float"
          onClick={() => navigate('/book-ride')}
        >
          <Map
            center={mapCenter}
            markers={mapMarkers}
            interactive={false}
          />
          {/* Map overlay CTA */}
          <div className="absolute inset-0 bg-gradient-to-t from-[#05070A]/70 via-transparent to-transparent pointer-events-none" />
          <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-xs font-semibold text-gray-200">
                {mapMarkers.length > 0 ? 'Location acquired' : 'Map ready'}
              </span>
            </div>
            <span className="bg-[#101820]/90 backdrop-blur-md border border-[#1E293B] px-3.5 py-1.5 rounded-full text-xs font-semibold flex items-center gap-2 text-[#38BDF8] shadow-lg opacity-0 group-hover:opacity-100 transition-opacity">
              <Navigation size={13} />
              Tap to book
            </span>
          </div>
        </div>

        {/* Right sidebar — Quick actions + Recent rides */}
        <div className="lg:col-span-5 flex flex-col gap-4">

          {/* Quick action tiles */}
          <div className="grid grid-cols-2 gap-3">
            {[
              {
                to: '/book-ride',
                icon: <Navigation size={20} />,
                label: 'Book Ride',
                sub: 'Instant dispatch',
                iconColor: 'text-[#38BDF8]',
                iconBg: 'bg-[#38BDF8]/10',
                hoverBorder: 'hover:border-[#38BDF8]/50',
              },
              {
                to: '/assistant',
                icon: <Bot size={20} />,
                label: 'Nova AI',
                sub: 'Voice · Text · Image',
                iconColor: 'text-violet-400',
                iconBg: 'bg-violet-500/10',
                hoverBorder: 'hover:border-violet-500/40',
              },
              {
                to: '/rides',
                icon: <Clock size={20} />,
                label: 'My Rides',
                sub: 'History & receipts',
                iconColor: 'text-amber-400',
                iconBg: 'bg-amber-500/10',
                hoverBorder: 'hover:border-amber-500/40',
              },
              {
                to: '/payments',
                icon: <CreditCard size={20} />,
                label: 'Payments',
                sub: 'Fares & ledger',
                iconColor: 'text-emerald-400',
                iconBg: 'bg-emerald-500/10',
                hoverBorder: 'hover:border-emerald-500/40',
              },
            ].map((item, i) => (
              <Link
                key={i}
                to={item.to}
                className={`card-interactive p-4 rounded-xl flex flex-col items-start gap-2.5 group ${item.hoverBorder}`}
              >
                <div className={`w-10 h-10 rounded-xl ${item.iconBg} ${item.iconColor} flex items-center justify-center border border-[#1E293B] group-hover:scale-105 transition-transform`}>
                  {item.icon}
                </div>
                <div>
                  <p className="text-sm font-semibold text-[#F5F7FA]">{item.label}</p>
                  <p className="text-[10px] text-gray-500">{item.sub}</p>
                </div>
              </Link>
            ))}
          </div>

          {/* Recent rides */}
          <div className="card flex-1 p-4 rounded-2xl bg-[#0A0F14] border border-[#1E293B]">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-[#F5F7FA]">Recent Journeys</h3>
              <Link to="/rides" className="text-[11px] font-semibold text-[#38BDF8] hover:underline flex items-center gap-0.5">
                All <ChevronRight size={13} />
              </Link>
            </div>

            {loading ? (
              <div className="space-y-2.5">
                {[1, 2].map(i => (
                  <div key={i} className="animate-pulse flex gap-3 p-3 bg-[#101820] rounded-xl border border-[#1E293B]">
                    <div className="w-9 h-9 bg-gray-800 rounded-lg shrink-0" />
                    <div className="flex-1 space-y-1.5 py-0.5">
                      <div className="h-3 bg-gray-800 rounded w-3/4" />
                      <div className="h-2.5 bg-gray-800 rounded w-1/3" />
                    </div>
                  </div>
                ))}
              </div>
            ) : recentRides.length > 0 ? (
              <div className="space-y-2">
                {recentRides.slice(0, 3).map((ride) => (
                  <Link
                    to={`/rides/${ride.id}`}
                    key={ride.id}
                    className="card-interactive flex items-center justify-between p-3 rounded-xl bg-[#101820] border border-[#1E293B] hover:border-[#38BDF8]/30 transition-all group"
                  >
                    <div className="flex items-center gap-3 overflow-hidden">
                      <div className="w-9 h-9 rounded-xl bg-[#0A0F14] border border-[#1E293B] text-gray-500 flex items-center justify-center shrink-0 group-hover:text-[#38BDF8] transition-colors">
                        <MapPin size={15} />
                      </div>
                      <div className="truncate">
                        <p className="text-xs font-semibold text-[#F5F7FA] truncate">
                          {ride.dropoff_location}
                        </p>
                        <p className="text-[10px] text-gray-500 mt-0.5">
                          {formatDistanceToNow(new Date(ride.created_at), { addSuffix: true })}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {ride.fare && (
                        <span className="text-xs font-mono font-bold text-[#F5F7FA]">
                          ₹{Number(ride.fare).toFixed(0)}
                        </span>
                      )}
                      <ChevronRight size={13} className="text-gray-600 group-hover:text-[#38BDF8] transition-colors" />
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <Navigation size={22} className="text-gray-600 mx-auto mb-2" />
                <p className="text-xs text-gray-400 font-medium">No journeys yet</p>
                <p className="text-[11px] text-gray-600 mt-0.5">Your first ride will appear here.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
