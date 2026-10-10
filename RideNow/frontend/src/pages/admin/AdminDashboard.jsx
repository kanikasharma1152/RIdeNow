import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  getAdminOverview,
  getAdminAIInsights,
  getMLDemandHotspots,
  getSystemHealth,
  getAdminIntelligence,
  getRideReliability,
} from '../../services/adminService';
import { useSocket } from '../../context/WebSocketContext';
import Map from '../../components/Map';
import {
  Users,
  Car,
  TrendingUp,
  Percent,
  MapPin,
  Sparkles,
  Bot,
  Activity,
  Calendar,
  AlertTriangle,
  Compass,
  ArrowUpRight,
  ShieldCheck,
  ShieldAlert,
  RefreshCw,
  Zap,
  Radio,
  Clock,
  Flame,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import toast from 'react-hot-toast';
import safetyService from '../../services/safetyService';

export default function AdminDashboard() {
  const { isConnected: isWsConnected, subscribe } = useSocket();
  const [data, setData] = useState(null);
  const [insights, setInsights] = useState(null);
  const [mlHotspots, setMlHotspots] = useState([]);
  const [fleetDrivers, setFleetDrivers] = useState([]);
  const [safetyMetrics, setSafetyMetrics] = useState(null);
  const [safetyEvents, setSafetyEvents] = useState([]);
  const [systemHealth, setSystemHealth] = useState(null);
  const [reliabilityData, setReliabilityData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingInsights, setLoadingInsights] = useState(false);
  const [selectedFilter, setSelectedFilter] = useState('ALL'); // 'ALL' | 'ONLINE' | 'OFFLINE'

  const loadDashboardData = useCallback(async () => {
    try {
      setLoading(true);
      const [overviewRes, hotspotsRes, safetyMetricsRes, safetyEventsRes, healthRes, reliabilityRes] = await Promise.allSettled([
        getAdminOverview(),
        getMLDemandHotspots(8),
        safetyService.getAdminSafetyMetrics(),
        safetyService.getAdminSafetyEvents({ limit: 6 }),
        getSystemHealth(),
        getRideReliability(),
      ]);

      if (overviewRes.status === 'fulfilled') {
        setData(overviewRes.value);
        if (overviewRes.value?.fleet_drivers) {
          setFleetDrivers(overviewRes.value.fleet_drivers);
        }
      }

      if (healthRes.status === 'fulfilled') {
        setSystemHealth(healthRes.value);
      }

      if (reliabilityRes.status === 'fulfilled') {
        setReliabilityData(reliabilityRes.value);
      }

      if (hotspotsRes.status === 'fulfilled') {
        const rawHotspots = hotspotsRes.value?.data || hotspotsRes.value || [];
        setMlHotspots(Array.isArray(rawHotspots) ? rawHotspots : []);
      }

      if (safetyMetricsRes.status === 'fulfilled') {
        setSafetyMetrics(safetyMetricsRes.value);
      }

      if (safetyEventsRes.status === 'fulfilled') {
        const evs = safetyEventsRes.value?.events || safetyEventsRes.value || [];
        setSafetyEvents(Array.isArray(evs) ? evs : []);
      }

      // Fetch AI operational insights in parallel
      fetchAIInsights();
    } catch (err) {
      console.error('Failed to load admin analytics:', err);
      toast.error('Unable to fetch mobility platform analytics');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchAIInsights = async () => {
    try {
      setLoadingInsights(true);
      const res = await getAdminAIInsights();
      setInsights(res);
    } catch (err) {
      console.error('Failed to generate AI insights:', err);
    } finally {
      setLoadingInsights(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  // Real-time WebSocket updates for driver locations & dispatch events
  useEffect(() => {
    const unsubscribe = subscribe((event) => {
      if (event.type === 'driver_location' && event.data) {
        setFleetDrivers((prev) => {
          const index = prev.findIndex((d) => d.id === event.data.driver_id || d.user_id === event.data.user_id);
          if (index !== -1) {
            const updated = [...prev];
            updated[index] = {
              ...updated[index],
              latitude: event.data.latitude,
              longitude: event.data.longitude,
              is_online: true,
              location_updated_at: new Date().toISOString(),
            };
            return updated;
          }
          return prev;
        });
      }
      if (event.type === 'ride_status_updated' || event.type === 'new_ride_request') {
        // Soft refresh summary metrics
        getAdminOverview().then((res) => {
          if (res) {
            setData(res);
            if (res.fleet_drivers) setFleetDrivers(res.fleet_drivers);
          }
        }).catch(() => {});
      }
    });

    return () => {
      if (unsubscribe) unsubscribe();
    };
  }, [subscribe]);

  const overview = data?.overview || {};
  const trend7d = data?.trend_7d || [];
  const topHotspots = data?.top_hotspots || [];

  // Filtered drivers for the fleet table
  const filteredDrivers = useMemo(() => {
    if (selectedFilter === 'ONLINE') return fleetDrivers.filter((d) => d.is_online);
    if (selectedFilter === 'OFFLINE') return fleetDrivers.filter((d) => !d.is_online);
    return fleetDrivers;
  }, [fleetDrivers, selectedFilter]);

  // Build Map Markers: combining live online drivers + ML demand hotspots
  const mapMarkers = useMemo(() => {
    const markers = [];

    // 1. Online driver positions
    fleetDrivers.forEach((driver) => {
      if (driver.latitude && driver.longitude && driver.is_online) {
        markers.push({
          id: `driver-${driver.id}`,
          lat: Number(driver.latitude),
          lng: Number(driver.longitude),
          type: 'driver',
          popup: `${driver.name} • ${driver.vehicle_model || driver.vehicle_type} (${driver.is_available ? 'Available' : 'Busy'})`,
        });
      }
    });

    // 2. ML Demand Hotspot zones
    mlHotspots.forEach((hs, idx) => {
      const lat = hs.latitude ?? hs.zone?.lat;
      const lng = hs.longitude ?? hs.zone?.lon;
      if (lat != null && lng != null) {
        markers.push({
          id: `hotspot-${hs.zone_id || idx}`,
          lat: Number(lat),
          lng: Number(lng),
          type: 'hotspot',
          popup: `Demand Hotspot: ${hs.zone_id || hs.label || `Zone #${idx + 1}`} (Score: ${Number(hs.current_demand_score || hs.demand_score || hs.surge_factor || 1.0).toFixed(1)}x)`,
        });
      }
    });

    return markers;
  }, [fleetDrivers, mlHotspots]);

  // Relative trend bars calculations
  const maxRides = Math.max(...trend7d.map((t) => t.rides || 1), 1);
  const maxRevenue = Math.max(...trend7d.map((t) => t.revenue || 1), 1);

  return (
    <div className="space-y-8 animate-fade-in pb-16">
      {/* ── Command Bar / Top Banner ─────────────────────────────────── */}
      <div className="card-panel relative overflow-hidden bg-gradient-to-r from-bg-secondary via-brand-950/20 to-bg-secondary border border-border-default flex flex-col md:flex-row md:items-center justify-between gap-6 p-6 rounded-2xl shadow-xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-brand-500/5 rounded-full blur-3xl pointer-events-none" />

        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-brand-500/10 border border-brand-500/20 text-brand-400 text-xs font-semibold uppercase tracking-wider">
              <Activity className="w-3.5 h-3.5 animate-pulse" />
              Live Mobility Command Center
            </span>
            <span
              className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono border ${
                isWsConnected
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                  : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
              }`}
            >
              <Radio className="w-3 h-3" />
              {isWsConnected ? 'WS LIVE' : 'WS CONNECTING'}
            </span>
          </div>
          <h1 className="text-2xl lg:text-3xl font-bold text-white tracking-tight">
            City Fleet Telemetry & Intelligence
          </h1>
          <p className="text-gray-400 text-sm mt-1 max-w-xl">
            Real-time aggregate platform operations, driver capacity analytics, and AI-synthesized executive briefings.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadDashboardData}
            disabled={loading}
            className="px-4 py-2.5 rounded-xl bg-bg-tertiary border border-border-default hover:bg-border-default text-gray-300 text-xs font-semibold transition-colors flex items-center gap-2 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh Data
          </button>
          <button
            onClick={fetchAIInsights}
            disabled={loadingInsights}
            className="btn-primary px-4 py-2.5 rounded-xl text-xs font-bold flex items-center gap-2 shadow-glow cursor-pointer"
          >
            <Sparkles className="w-4 h-4" />
            Re-run AI Analysis
          </button>
        </div>
      </div>

      {/* ── 4 Key Performance Indicators ────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* KPI 1: Total Users */}
        <div className="card-panel p-5 relative overflow-hidden group hover:border-brand-500/40 transition-colors rounded-2xl bg-[#0A0F14] border border-[#1E293B]">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">Total Users</span>
            <div className="w-10 h-10 rounded-xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400">
              <Users className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4">
            <h3 className="text-3xl font-bold text-white">
              {loading ? '--' : overview.total_users ?? 0}
            </h3>
            <p className="text-xs text-gray-400 mt-1 flex items-center gap-1.5">
              <span>{overview.total_drivers ?? fleetDrivers.length} registered fleet drivers</span>
            </p>
          </div>
        </div>

        {/* KPI 2: Active Drivers Online */}
        <div className="card-panel p-5 relative overflow-hidden group hover:border-emerald-500/40 transition-colors rounded-2xl bg-[#0A0F14] border border-[#1E293B]">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">Active Drivers</span>
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <Car className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4">
            <h3 className="text-3xl font-bold text-emerald-400 flex items-center gap-2">
              {loading ? '--' : overview.active_drivers_online ?? 0}
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            </h3>
            <p className="text-xs text-gray-400 mt-1">
              Online & dispatch ready across city
            </p>
          </div>
        </div>

        {/* KPI 3: Gross Revenue */}
        <div className="card-panel p-5 relative overflow-hidden group hover:border-brand-500/40 transition-colors rounded-2xl bg-[#0A0F14] border border-[#1E293B]">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">Gross Revenue</span>
            <div className="w-10 h-10 rounded-xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400">
              <TrendingUp className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4">
            <h3 className="text-3xl font-bold text-white">
              {loading ? '--' : `₹${Number(overview.total_revenue_inr || 0).toLocaleString()}`}
            </h3>
            <p className="text-xs text-gray-400 mt-1">
              {overview.completed_rides ?? 0} settled transactions
            </p>
          </div>
        </div>

        {/* KPI 4: Completion Rate */}
        <div className="card-panel p-5 relative overflow-hidden group hover:border-cyan-500/40 transition-colors rounded-2xl bg-[#0A0F14] border border-[#1E293B]">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">Completion Rate</span>
            <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
              <Percent className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4">
            <h3 className="text-3xl font-bold text-cyan-400">
              {loading ? '--' : `${overview.completion_rate_pct ?? 0}%`}
            </h3>
            <p className="text-xs text-gray-400 mt-1">
              {overview.cancelled_rides ?? 0} cancellations recorded
            </p>
          </div>
        </div>
      </div>

      {/* ── Live Fleet & Demand Hotspots Map ────────────────────────── */}
      <div className="card-panel p-6 rounded-2xl bg-[#0A0F14] border border-[#1E293B] shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Compass className="w-4 h-4 text-[#38BDF8]" />
              Live City Fleet Radar & Demand Heatmap
            </h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Real-time driver GPS locations (animated via WebSocket) and predictive ML surge zones
            </p>
          </div>

          <div className="flex items-center gap-4 text-xs font-mono">
            <div className="flex items-center gap-1.5 text-gray-300">
              <span className="w-2.5 h-2.5 rounded-full bg-[#38BDF8]" />
              <span>Active Drivers ({fleetDrivers.filter((d) => d.is_online).length})</span>
            </div>
            <div className="flex items-center gap-1.5 text-gray-300">
              <span className="w-2.5 h-2.5 rounded-full bg-orange-400" />
              <span>ML Demand Hotspots ({mlHotspots.length})</span>
            </div>
          </div>
        </div>

        <div className="h-[360px] md:h-[440px] rounded-xl overflow-hidden border border-[#1E293B] relative">
          <Map markers={mapMarkers} animateDrivers={true} />
        </div>
      </div>

      {/* ── Main Intelligence Grid: 7-Day Trend + AI Insights ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: 7-Day Ride Volume & Revenue Trend (7 Cols) */}
        <div className="lg:col-span-7 card-panel p-6 rounded-2xl bg-[#0A0F14] border border-[#1E293B] flex flex-col justify-between shadow-xl">
          <div>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-brand-400" />
                  7-Day Ride Volume & Revenue Trend
                </h2>
                <p className="text-xs text-gray-400 mt-0.5">
                  Aggregated from completed rides database over the rolling 7-day period.
                </p>
              </div>
              <div className="flex items-center gap-3 text-xs">
                <span className="flex items-center gap-1 text-brand-400">
                  <span className="w-2.5 h-2.5 rounded-sm bg-brand-400" /> Rides
                </span>
                <span className="flex items-center gap-1 text-emerald-400">
                  <span className="w-2.5 h-2.5 rounded-sm bg-emerald-400" /> Revenue
                </span>
              </div>
            </div>

            {loading ? (
              <div className="py-16 text-center text-gray-400 text-xs">Loading trend metrics...</div>
            ) : trend7d.length === 0 ? (
              <div className="py-16 text-center text-gray-500 text-xs">
                No ride activity recorded in the last 7 days.
              </div>
            ) : (
              <div className="space-y-4 my-2">
                {trend7d.map((day, idx) => {
                  const ridePct = Math.round((day.rides / maxRides) * 100);
                  const revPct = Math.round((day.revenue / maxRevenue) * 100);

                  return (
                    <div
                      key={idx}
                      className="space-y-1.5 p-3 rounded-xl bg-bg-tertiary/40 border border-border-default"
                    >
                      <div className="flex justify-between items-center text-xs">
                        <span className="font-mono text-gray-300 font-semibold">{day.date}</span>
                        <div className="flex items-center gap-4">
                          <span className="text-brand-400 font-medium">{day.rides} rides</span>
                          <span className="text-emerald-400 font-bold">
                            ₹{Number(day.revenue).toLocaleString()}
                          </span>
                        </div>
                      </div>

                      {/* Stacked visualization bars */}
                      <div className="grid grid-cols-2 gap-2 pt-1">
                        <div className="w-full bg-bg-secondary rounded-full h-2 overflow-hidden">
                          <div
                            className="bg-brand-400 h-full rounded-full transition-all duration-700"
                            style={{ width: `${Math.max(ridePct, 4)}%` }}
                          />
                        </div>
                        <div className="w-full bg-bg-secondary rounded-full h-2 overflow-hidden">
                          <div
                            className="bg-emerald-400 h-full rounded-full transition-all duration-700"
                            style={{ width: `${Math.max(revPct, 4)}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="mt-6 pt-4 border-t border-border-default flex items-center justify-between text-xs text-gray-400">
            <span>
              Average Distance: <strong className="text-white">{overview.average_distance_km ?? 0} km</strong>
            </span>
            <span>
              Total Rides Tracked: <strong className="text-white">{overview.total_rides ?? 0}</strong>
            </span>
          </div>
        </div>

        {/* Right: AI Operational Insights Card (5 Cols) */}
        <div className="lg:col-span-5 card-panel p-6 rounded-2xl bg-gradient-to-b from-[#0A0F14] to-brand-950/20 border border-brand-500/30 flex flex-col justify-between shadow-glow">
          <div>
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-border-default">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-brand-500/20 border border-brand-500/30 flex items-center justify-center text-brand-400">
                  <Bot className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">Chief Operations AI</h3>
                  <span className="text-[11px] text-brand-400 font-mono">AI Intelligence Engine</span>
                </div>
              </div>
              <span className="px-2 py-0.5 rounded-md bg-brand-500/10 text-brand-400 border border-brand-500/20 text-[10px] uppercase font-bold">
                Executive Briefing
              </span>
            </div>

            {loadingInsights ? (
              <div className="py-12 text-center space-y-3">
                <Sparkles className="w-8 h-8 text-brand-400 animate-spin mx-auto" />
                <p className="text-xs text-gray-400">AI is synthesizing platform telemetry...</p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="p-4 rounded-xl bg-bg-tertiary/60 border border-border-default text-xs text-gray-200 leading-relaxed whitespace-pre-line">
                  {insights?.ai_insights ||
                    'Platform telemetry stable. Recommendations will update based on current driver utilization and booking velocity.'}
                </div>

                <div className="p-3 rounded-xl bg-brand-500/5 border border-brand-500/20 flex items-start gap-2.5 text-xs text-brand-300">
                  <Zap className="w-4 h-4 text-brand-400 shrink-0 mt-0.5" />
                  <span>
                    Auto-tuned suggestions are generated directly from real PostgreSQL transaction records.
                  </span>
                </div>
              </div>
            )}
          </div>

          <div className="mt-6 pt-4 border-t border-border-default flex items-center justify-between text-[11px] text-gray-400">
            <span>Autonomous Operations Core</span>
            <span>Zero Hallucination Grounded</span>
          </div>
        </div>
      </div>

      {/* ── Driver Fleet Table ─────────────────────────────────────── */}
      <div className="card-panel p-6 rounded-2xl bg-[#0A0F14] border border-[#1E293B] shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-5">
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Car className="w-4 h-4 text-[#38BDF8]" />
              Driver Fleet Status & Capacity
            </h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Live status, vehicle specifications, and GPS availability
            </p>
          </div>

          <div className="flex items-center gap-1.5 p-1 bg-[#101820] border border-[#1E293B] rounded-xl">
            {['ALL', 'ONLINE', 'OFFLINE'].map((filter) => (
              <button
                key={filter}
                onClick={() => setSelectedFilter(filter)}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
                  selectedFilter === filter
                    ? 'bg-[#38BDF8] text-[#05070A]'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                {filter}
              </button>
            ))}
          </div>
        </div>

        {filteredDrivers.length === 0 ? (
          <div className="py-8 text-center text-xs text-gray-500">
            No drivers found matching filter: {selectedFilter}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#1E293B] text-[11px] font-mono uppercase text-gray-400">
                  <th className="pb-3 pl-2">Driver</th>
                  <th className="pb-3">Vehicle Details</th>
                  <th className="pb-3">Telemetry Status</th>
                  <th className="pb-3">Availability</th>
                  <th className="pb-3 pr-2 text-right">Coordinates</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1E293B] text-xs">
                {filteredDrivers.map((driver) => (
                  <tr key={driver.id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="py-3 pl-2 font-medium text-white flex items-center gap-2.5">
                      <div className="w-7 h-7 rounded-lg bg-[#101820] border border-[#1E293B] flex items-center justify-center text-gray-300 font-bold text-xs">
                        #{driver.id}
                      </div>
                      <div>
                        <div className="font-semibold text-gray-200">{driver.name}</div>
                        {driver.phone && (
                          <div className="text-[10px] text-gray-500 font-mono">{driver.phone}</div>
                        )}
                      </div>
                    </td>
                    <td className="py-3 text-gray-300">
                      <div>{driver.vehicle_model || driver.vehicle_type || 'RideNow Unit'}</div>
                      <div className="text-[10px] text-gray-500 font-mono uppercase">
                        {driver.vehicle_number || 'Standard Fleet'}
                      </div>
                    </td>
                    <td className="py-3">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${
                          driver.is_online
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            : 'bg-gray-500/10 text-gray-400 border border-gray-500/20'
                        }`}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            driver.is_online ? 'bg-emerald-400 animate-pulse' : 'bg-gray-500'
                          }`}
                        />
                        {driver.is_online ? 'ONLINE' : 'OFFLINE'}
                      </span>
                    </td>
                    <td className="py-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] font-mono ${
                          driver.is_available
                            ? 'text-cyan-400 bg-cyan-500/10'
                            : 'text-amber-400 bg-amber-500/10'
                        }`}
                      >
                        {driver.is_available ? 'DISPATCH READY' : 'ON TRIP / PAUSED'}
                      </span>
                    </td>
                    <td className="py-3 pr-2 text-right font-mono text-[11px] text-gray-400">
                      {driver.latitude && driver.longitude ? (
                        <span>
                          {Number(driver.latitude).toFixed(3)}, {Number(driver.longitude).toFixed(3)}
                        </span>
                      ) : (
                        <span className="text-gray-600">No GPS Fix</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Top Urban Pickup Hotspots ───────────────────────────────── */}
      <div className="card-panel p-6 rounded-2xl bg-[#0A0F14] border border-[#1E293B] shadow-xl">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <MapPin className="w-4 h-4 text-brand-400" />
              Top Urban Pickup Hotspots
            </h2>
            <p className="text-xs text-gray-400 mt-0.5">High volume pickup zones aggregated from user trip starts</p>
          </div>
          <span className="text-xs text-gray-400 font-medium">Top 5 Corridors</span>
        </div>

        {loading ? (
          <div className="py-8 text-center text-xs text-gray-400">Analyzing trip coordinates...</div>
        ) : topHotspots.length === 0 ? (
          <div className="py-8 text-center text-xs text-gray-500">No hotspot aggregations found yet.</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {topHotspots.map((h, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl bg-bg-tertiary/50 border border-border-default hover:border-brand-500/40 transition-colors flex items-center justify-between"
              >
                <div className="flex items-start gap-3">
                  <div className="w-7 h-7 rounded-lg bg-brand-500/10 border border-brand-500/20 text-brand-400 flex items-center justify-center text-xs font-bold shrink-0">
                    #{idx + 1}
                  </div>
                  <div>
                    <h4 className="text-xs font-semibold text-white truncate max-w-[200px]">{h.location}</h4>
                    <span className="text-[11px] text-gray-400 mt-0.5 block">High Origin Density</span>
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-xs font-bold text-brand-400 bg-brand-500/10 px-2 py-1 rounded-md border border-brand-500/20">
                    {h.count} Trips
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Safety Intelligence Command Center (Phase 13) ───────── */}
      <div className="card-panel p-6 rounded-2xl bg-[#0A0F14] border border-[#1E293B] shadow-xl space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-red-400" />
              Safety &amp; Trust Command Center
            </h2>
            <p className="text-xs text-gray-400 mt-0.5">Real-time safety events, SOS alerts, and corridor monitoring</p>
          </div>
          <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 w-fit">
            SHIELD ACTIVE
          </span>
        </div>

        {/* Safety KPI Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-[#101820] border border-[#1E293B]">
            <p className="text-[10px] text-gray-400 font-mono uppercase">Total Events</p>
            <p className="text-xl font-bold text-white mt-1">
              {safetyMetrics?.total_events ?? safetyMetrics?.events_today_count ?? safetyEvents.length ?? 0}
            </p>
          </div>
          <div className="p-4 rounded-xl bg-[#101820] border border-red-500/30">
            <p className="text-[10px] text-red-400 font-mono uppercase">SOS Alerts</p>
            <p className="text-xl font-bold text-red-400 mt-1">
              {safetyMetrics?.sos_count ?? safetyMetrics?.active_sos_count ?? 0}
            </p>
          </div>
          <div className="p-4 rounded-xl bg-[#101820] border border-amber-500/30">
            <p className="text-[10px] text-amber-400 font-mono uppercase">High Severity</p>
            <p className="text-xl font-bold text-amber-400 mt-1">
              {safetyMetrics?.high_severity_count ?? safetyMetrics?.unresolved_critical_count ?? 0}
            </p>
          </div>
          <div className="p-4 rounded-xl bg-[#101820] border border-emerald-500/30">
            <p className="text-[10px] text-emerald-400 font-mono uppercase">Resolved</p>
            <p className="text-xl font-bold text-emerald-400 mt-1">{safetyMetrics?.resolved_count ?? 0}</p>
          </div>
        </div>

        {/* Recent Safety Events Table */}
        <div>
          <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">Live Safety Feed</h3>
          {safetyEvents.length === 0 ? (
            <div className="py-6 text-center text-xs text-gray-500 border border-dashed border-[#1E293B] rounded-xl bg-[#101820]/40">
              No active safety events. All fleet operations nominal. ✓
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-[#1E293B] text-gray-500 font-mono text-[11px]">
                    <th className="pb-2">Event</th>
                    <th className="pb-2">Severity</th>
                    <th className="pb-2">Ride / User</th>
                    <th className="pb-2">Status</th>
                    <th className="pb-2 text-right">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1E293B]">
                  {safetyEvents.map((ev) => (
                    <tr key={ev.id} className="hover:bg-[#101820]/50 transition-colors">
                      <td className="py-2.5 font-semibold text-white">
                        {ev.event_type?.replace(/_/g, ' ')}
                      </td>
                      <td className="py-2.5">
                        <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                          ev.severity === 'CRITICAL' ? 'bg-red-500/10 text-red-400 border border-red-500/30' :
                          ev.severity === 'HIGH' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30' :
                          'bg-[#38BDF8]/10 text-[#38BDF8] border border-[#38BDF8]/30'
                        }`}>
                          {ev.severity}
                        </span>
                      </td>
                      <td className="py-2.5 text-gray-400 font-mono">
                        {ev.ride_id ? `Ride #${ev.ride_id}` : `User #${ev.user_id}`}
                      </td>
                      <td className="py-2.5">
                        <span className="text-[10px] font-mono uppercase text-gray-400">
                          {ev.status}
                        </span>
                      </td>
                      <td className="py-2.5 text-right font-mono text-gray-500 text-[11px]">
                        {(ev.created_at || ev.detected_at)
                          ? new Date(ev.created_at || ev.detected_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* ─── Phase 14: System Health Center & Ride Reliability ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* System Health Center */}
        <div className="card p-6 border border-[#1E293B] bg-[#0A0F14] rounded-2xl shadow-xl space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity size={18} className="text-[#38BDF8]" />
              <h2 className="text-base font-bold text-[#F5F7FA]">System Health Center</h2>
            </div>
            {systemHealth?.overall_status && (
              <span className={`text-[10px] font-mono uppercase px-2.5 py-0.5 rounded-full border ${
                systemHealth.overall_status === 'HEALTHY'
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : systemHealth.overall_status === 'DEGRADED'
                  ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                  : 'bg-red-500/10 text-red-400 border-red-500/30'
              }`}>
                {systemHealth.overall_status}
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            {systemHealth?.services ? (
              Object.entries(systemHealth.services).map(([name, svc]) => (
                <div key={name} className="p-3 bg-[#101820] border border-[#1E293B] rounded-xl text-xs space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-gray-300 capitalize">{name.replace(/_/g, ' ')}</span>
                    <span className={`w-2 h-2 rounded-full ${
                      svc.status === 'HEALTHY' ? 'bg-emerald-400' :
                      svc.status === 'DEGRADED' ? 'bg-amber-400' :
                      svc.status === 'UNAVAILABLE' ? 'bg-red-400' : 'bg-gray-500'
                    }`} />
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-gray-500 font-mono">
                    <span>{svc.status}</span>
                    {svc.latency_ms !== null && svc.latency_ms !== undefined && (
                      <span>{svc.latency_ms}ms</span>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <div className="col-span-2 text-center py-4 text-xs text-gray-500">
                Checking system health...
              </div>
            )}
          </div>
        </div>

        {/* Ride Reliability & Stale Detection */}
        <div className="card p-6 border border-[#1E293B] bg-[#0A0F14] rounded-2xl shadow-xl space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldCheck size={18} className="text-emerald-400" />
              <h2 className="text-base font-bold text-[#F5F7FA]">Ride Reliability Engine</h2>
            </div>
            {reliabilityData && (
              <span className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full border ${
                (reliabilityData.stale_rides_count || 0) === 0
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
              }`}>
                {reliabilityData.stale_rides_count || 0} Stale
              </span>
            )}
          </div>

          <div className="grid grid-cols-3 gap-2.5">
            <div className="p-3 bg-[#101820] border border-[#1E293B] rounded-xl text-center">
              <p className="text-[10px] font-mono uppercase text-gray-500">Active Rides</p>
              <p className="text-lg font-bold text-white mt-0.5">{reliabilityData?.active_rides_count ?? 0}</p>
            </div>
            <div className="p-3 bg-[#101820] border border-[#1E293B] rounded-xl text-center">
              <p className="text-[10px] font-mono uppercase text-gray-500">Cancelled (24h)</p>
              <p className="text-lg font-bold text-red-400 mt-0.5">{reliabilityData?.recent_cancellations_24h ?? 0}</p>
            </div>
            <div className="p-3 bg-[#101820] border border-[#1E293B] rounded-xl text-center">
              <p className="text-[10px] font-mono uppercase text-gray-500">Rejections (24h)</p>
              <p className="text-lg font-bold text-amber-400 mt-0.5">{reliabilityData?.recent_rejections_24h ?? 0}</p>
            </div>
          </div>

          {/* Stale Rides Inspection List */}
          <div>
            <p className="text-[11px] font-mono text-gray-400 uppercase tracking-wider mb-2">Stale Ride Inspection</p>
            {reliabilityData?.stale_rides?.length > 0 ? (
              <div className="space-y-2 max-h-32 overflow-y-auto">
                {reliabilityData.stale_rides.map((r) => (
                  <div key={r.ride_id} className="p-2.5 bg-[#101820] border border-amber-500/30 rounded-xl text-xs flex items-center justify-between">
                    <div>
                      <span className="font-mono text-white font-bold">Ride #{r.ride_id}</span>
                      <span className="ml-2 text-gray-400 text-[10px]">({r.status})</span>
                    </div>
                    <span className="text-amber-400 font-mono text-[11px] font-bold">
                      Stuck {r.stuck_for_minutes}m
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-3 bg-[#101820]/40 border border-[#1E293B] rounded-xl text-center text-xs text-gray-500">
                No stale rides detected. All dispatch flows within SLA. ✓
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
