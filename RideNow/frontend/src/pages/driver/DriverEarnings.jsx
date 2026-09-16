import { useState, useEffect } from 'react';
import { getDriverEarnings } from '../../services/driverService';
import { TrendingUp, Loader2, Calendar, CalendarDays, BarChart2, Car } from 'lucide-react';
import toast from 'react-hot-toast';

const StatCard = ({ icon: Icon, label, value, sub, highlight, color = 'brand' }) => (
  <div className={`card p-5 border flex items-start gap-4 transition-all rounded-2xl shadow-lg ${
    highlight
      ? 'bg-gradient-to-br from-[#0D1A27] via-[#101820] to-[#0A0F14] border-[#38BDF8]/40 shadow-[0_0_25px_rgba(56,189,248,0.15)]'
      : 'bg-[#0A0F14] border-[#1E293B]'
  }`}>
    <div className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 ${
      highlight
        ? 'bg-[#38BDF8] text-[#05070A] shadow-[0_0_15px_rgba(56,189,248,0.4)]'
        : color === 'emerald'
        ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-400'
        : 'bg-[#101820] border border-[#1E293B] text-[#38BDF8]'
    }`}>
      <Icon size={22} />
    </div>
    <div>
      <p className="text-xs font-medium mb-1 text-gray-400 uppercase tracking-wider">{label}</p>
      <p className={`text-3xl font-bold ${highlight ? 'text-[#F5F7FA]' : 'text-emerald-400'}`}>{value}</p>
      {sub && <p className="text-xs mt-1 text-gray-500 font-mono">{sub}</p>}
    </div>
  </div>
);

const DriverEarnings = () => {
  const [earnings, setEarnings] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchEarnings = async () => {
      try {
        const data = await getDriverEarnings();
        setEarnings(data);
      } catch (err) {
        toast.error('Failed to load earnings data');
      } finally {
        setLoading(false);
      }
    };
    fetchEarnings();
  }, []);

  if (loading) return (
    <div className="flex h-[60vh] items-center justify-center">
      <Loader2 className="w-8 h-8 animate-spin text-[#38BDF8]" />
    </div>
  );

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-fade-in pb-16">
      {/* Header */}
      <div className="card-panel relative overflow-hidden bg-gradient-to-r from-[#0D141B] via-[#101820] to-[#0A0F14] border border-[#1E293B] rounded-2xl p-6 md:p-8 shadow-xl">
        <div className="absolute top-0 right-0 w-80 h-80 bg-[#38BDF8]/5 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10">
          <div className="inline-flex items-center gap-2 bg-[#101820] border border-[#38BDF8]/30 text-[#38BDF8] text-xs font-mono px-3 py-1 rounded-full mb-3">
            <TrendingUp size={12} />
            EARNINGS TELEMETRY
          </div>
          <h2 className="text-2xl md:text-3xl font-bold text-[#F5F7FA] tracking-tight">Driver Earnings</h2>
          <p className="text-gray-400 mt-1 text-sm">Track your payout revenue, ride performance, and metrics.</p>
        </div>
      </div>

      {!earnings ? (
        <div className="card p-16 text-center border border-[#1E293B] bg-[#0A0F14] rounded-2xl">
          <div className="w-14 h-14 rounded-2xl bg-[#101820] border border-[#1E293B] flex items-center justify-center text-gray-500 mx-auto mb-4">
            <TrendingUp className="w-7 h-7" />
          </div>
          <h3 className="text-xl font-bold text-[#F5F7FA] mb-2">No earnings yet</h3>
          <p className="text-gray-400 text-sm">Complete your first ride to start tracking earnings.</p>
        </div>
      ) : (
        <>
          {/* Top highlight stat */}
          <StatCard
            icon={TrendingUp}
            label="Total Lifetime Earnings"
            value={`₹${Number(earnings.total_earnings || 0).toFixed(2)}`}
            sub={`${earnings.total_rides || 0} completed rides across all shifts`}
            highlight
          />

          {/* Breakdown Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            <StatCard
              icon={Calendar}
              label="Today"
              value={`₹${Number(earnings.today_earnings || 0).toFixed(2)}`}
              sub="Today's shift earnings"
              color="emerald"
            />
            <StatCard
              icon={CalendarDays}
              label="This Week"
              value={`₹${Number(earnings.week_earnings || 0).toFixed(2)}`}
              sub="Last 7 days"
              color="emerald"
            />
            <StatCard
              icon={BarChart2}
              label="This Month"
              value={`₹${Number(earnings.month_earnings || 0).toFixed(2)}`}
              sub="Last 30 days"
              color="emerald"
            />
          </div>

          {/* Performance Summary */}
          <div className="card p-6 border border-[#1E293B] bg-[#0A0F14] rounded-2xl shadow-lg">
            <h3 className="font-bold text-[#F5F7FA] text-lg mb-6">Performance Summary</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
              <div className="p-5 rounded-xl bg-[#101820] border border-[#1E293B]">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Average Fare</p>
                <p className="text-2xl font-bold text-emerald-400">₹{Number(earnings.average_fare || 0).toFixed(2)}</p>
              </div>
              <div className="p-5 rounded-xl bg-[#101820] border border-[#1E293B]">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Completed Rides</p>
                <p className="text-2xl font-bold text-[#F5F7FA]">{earnings.total_rides || 0}</p>
              </div>
              <div className="p-5 rounded-xl bg-[#101820] border border-[#1E293B]">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Cancelled Rides</p>
                <p className="text-2xl font-bold text-red-400">{earnings.cancelled_rides || 0}</p>
              </div>
            </div>
            <div className="mt-6 pt-5 border-t border-[#1E293B]">
              <div className="flex items-center gap-3 text-xs text-gray-400 font-mono">
                <Car size={16} className="text-[#38BDF8]" />
                Earnings are calculated based on fare charged to passengers for completed trips.
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default DriverEarnings;
