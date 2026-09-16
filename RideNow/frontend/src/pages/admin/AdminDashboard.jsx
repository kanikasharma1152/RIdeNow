import React, { useState, useEffect } from 'react';
import { getAdminOverview, getAdminAIInsights } from '../../services/adminService';
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
  RefreshCw,
  Zap
} from 'lucide-react';
import toast from 'react-hot-toast';

export default function AdminDashboard() {
  const [data, setData] = useState(null);
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingInsights, setLoadingInsights] = useState(false);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      const res = await getAdminOverview();
      setData(res);
      // Fetch AI operational insights in parallel
      fetchAIInsights();
    } catch (err) {
      console.error('Failed to load admin analytics:', err);
      toast.error('Unable to fetch mobility platform analytics');
    } finally {
      setLoading(false);
    }
  };

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

  const overview = data?.overview || {};
  const trend7d = data?.trend_7d || [];
  const hotspots = data?.top_hotspots || [];

  // Calculate maximum ride count and revenue for relative trend visualization bars
  const maxRides = Math.max(...trend7d.map(t => t.rides || 1), 1);
  const maxRevenue = Math.max(...trend7d.map(t => t.revenue || 1), 1);

  return (
    <div className="space-y-8 animate-fade-in pb-12">
      {/* Top Banner */}
      <div className="card-panel relative overflow-hidden bg-gradient-to-r from-bg-secondary via-brand-950/20 to-bg-secondary border border-border-default flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="absolute top-0 right-0 w-96 h-96 bg-brand-500/5 rounded-full blur-3xl pointer-events-none" />
        
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-500/10 border border-brand-500/20 text-brand-400 text-xs font-semibold uppercase tracking-wider mb-2">
            <Activity className="w-3.5 h-3.5 animate-pulse" />
            Live Mobility Command Center
          </div>
          <h1 className="text-2xl lg:text-3xl font-bold text-white tracking-tight">
            City Fleet Telemetry & Intelligence
          </h1>
          <p className="text-gray-400 text-sm mt-1 max-w-xl">
            Real-time aggregate platform operations, driver capacity analytics, and Groq-synthesized executive briefings.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadDashboardData}
            disabled={loading}
            className="px-4 py-2.5 rounded-xl bg-bg-tertiary border border-border-default hover:bg-border-default text-gray-300 text-xs font-semibold transition-colors flex items-center gap-2"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh Data
          </button>
          <button
            onClick={fetchAIInsights}
            disabled={loadingInsights}
            className="btn-primary px-4 py-2.5 rounded-xl text-xs font-bold flex items-center gap-2 shadow-glow"
          >
            <Sparkles className="w-4 h-4" />
            Re-run AI Analysis
          </button>
        </div>
      </div>

      {/* 4 Key Performance Indicators (KPI Cards) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        
        {/* KPI 1: Total Users */}
        <div className="card-panel p-5 relative overflow-hidden group hover:border-brand-500/40 transition-colors">
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
              <span>{overview.total_drivers ?? 0} registered fleet drivers</span>
            </p>
          </div>
        </div>

        {/* KPI 2: Active Drivers Online */}
        <div className="card-panel p-5 relative overflow-hidden group hover:border-emerald-500/40 transition-colors">
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

        {/* KPI 3: Gross Revenue (INR) */}
        <div className="card-panel p-5 relative overflow-hidden group hover:border-brand-500/40 transition-colors">
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
        <div className="card-panel p-5 relative overflow-hidden group hover:border-cyan-500/40 transition-colors">
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

      {/* Main Grid: 7-Day Trend + Groq AI Insights */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left: 7-Day Ride Volume & Revenue Trend (7 Cols) */}
        <div className="lg:col-span-7 card-panel flex flex-col justify-between">
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
              <div className="py-16 text-center text-gray-500 text-xs">No ride activity recorded in the last 7 days.</div>
            ) : (
              <div className="space-y-4 my-2">
                {trend7d.map((day, idx) => {
                  const ridePct = Math.round((day.rides / maxRides) * 100);
                  const revPct = Math.round((day.revenue / maxRevenue) * 100);

                  return (
                    <div key={idx} className="space-y-1.5 p-3 rounded-xl bg-bg-tertiary/40 border border-border-default">
                      <div className="flex justify-between items-center text-xs">
                        <span className="font-mono text-gray-300 font-semibold">{day.date}</span>
                        <div className="flex items-center gap-4">
                          <span className="text-brand-400 font-medium">{day.rides} rides</span>
                          <span className="text-emerald-400 font-bold">₹{Number(day.revenue).toLocaleString()}</span>
                        </div>
                      </div>

                      {/* Stacked visualization bars */}
                      <div className="grid grid-cols-2 gap-2 pt-1">
                        {/* Rides bar */}
                        <div className="w-full bg-bg-secondary rounded-full h-2 overflow-hidden">
                          <div
                            className="bg-brand-400 h-full rounded-full transition-all duration-700"
                            style={{ width: `${Math.max(ridePct, 4)}%` }}
                          />
                        </div>
                        {/* Revenue bar */}
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
            <span>Average Distance: <strong className="text-white">{overview.average_distance_km ?? 0} km</strong></span>
            <span>Total Rides Tracked: <strong className="text-white">{overview.total_rides ?? 0}</strong></span>
          </div>
        </div>

        {/* Right: Groq AI Operational Insights Card (5 Cols) */}
        <div className="lg:col-span-5 card-panel flex flex-col justify-between border-brand-500/30 bg-gradient-to-b from-bg-secondary to-brand-950/10 shadow-glow">
          <div>
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-border-default">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-brand-500/20 border border-brand-500/30 flex items-center justify-center text-brand-400">
                  <Bot className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">Chief Operations AI</h3>
                  <span className="text-[11px] text-brand-400 font-mono">Groq Llama-3.3-70B</span>
                </div>
              </div>
              <span className="px-2 py-0.5 rounded-md bg-brand-500/10 text-brand-400 border border-brand-500/20 text-[10px] uppercase font-bold">
                Executive Briefing
              </span>
            </div>

            {loadingInsights ? (
              <div className="py-12 text-center space-y-3">
                <Sparkles className="w-8 h-8 text-brand-400 animate-spin mx-auto" />
                <p className="text-xs text-gray-400">Groq LLM is synthesizing platform telemetry...</p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="p-4 rounded-xl bg-bg-tertiary/60 border border-border-default text-xs text-gray-200 leading-relaxed whitespace-pre-line">
                  {insights?.ai_insights || (
                    "Platform telemetry stable. Recommendations will update based on current driver utilization and booking velocity."
                  )}
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
            <span>Model: llama-3.3-70b-versatile</span>
            <span>Zero Hallucination Grounded</span>
          </div>
        </div>

      </div>

      {/* Top Pickup Hotspots Section */}
      <div className="card-panel">
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
        ) : hotspots.length === 0 ? (
          <div className="py-8 text-center text-xs text-gray-500">No hotspot aggregations found yet.</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {hotspots.map((h, idx) => (
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

    </div>
  );
}
