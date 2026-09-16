import { CheckCircle2, Clock3, MapPin, Navigation, XCircle } from 'lucide-react';

const statusStyle = {
  REQUESTED: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
  PENDING: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
  ACCEPTED: 'bg-sky-500/10 text-sky-300 border-sky-500/30',
  ASSIGNED: 'bg-sky-500/10 text-sky-300 border-sky-500/30',
  STARTED: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30',
  IN_PROGRESS: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30',
  COMPLETED: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
  PAID: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
  CANCELLED: 'bg-rose-500/10 text-rose-300 border-rose-500/30',
  FAILED: 'bg-rose-500/10 text-rose-300 border-rose-500/30',
  REFUNDED: 'bg-violet-500/10 text-violet-300 border-violet-500/30',
};

export function StatusBadge({ status, className = '' }) {
  const normalized = (status || 'PENDING').toUpperCase();
  const Icon = normalized === 'COMPLETED' || normalized === 'PAID' ? CheckCircle2
    : normalized === 'CANCELLED' || normalized === 'FAILED' ? XCircle
      : normalized === 'STARTED' || normalized === 'IN_PROGRESS' ? Navigation : Clock3;
  return <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold tracking-wide ${statusStyle[normalized] || 'bg-slate-500/10 text-slate-300 border-slate-500/30'} ${className}`}><Icon size={12} />{normalized.replace('_', ' ')}</span>;
}

export function MetricCard({ label, value, icon: Icon, tone = 'cyan' }) {
  const tones = { cyan: 'text-[#38BDF8] bg-[#38BDF8]/10 border-[#38BDF8]/20', emerald: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/20', amber: 'text-amber-300 bg-amber-500/10 border-amber-500/20' };
  return <div className="card-interactive p-4 min-w-0"><div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-gray-500 font-semibold">{Icon && <Icon size={14} className={tones[tone].split(' ')[0]} />}{label}</div><p className="mt-2 text-xl font-bold text-white truncate">{value}</p></div>;
}

export function RouteBlock({ pickup, destination }) {
  return <div className="relative space-y-4 pl-1"><div className="absolute left-3 top-5 bottom-5 w-px bg-[#263647]" /><div className="relative flex gap-3"><span className="mt-1.5 grid h-6 w-6 place-items-center rounded-full border-2 border-[#38BDF8] bg-[#101820]"><span className="h-1.5 w-1.5 rounded-full bg-[#38BDF8]" /></span><div className="min-w-0"><p className="text-[10px] uppercase tracking-wider font-semibold text-gray-500">Pickup</p><p className="mt-0.5 text-sm font-medium text-white break-words">{pickup || 'Pickup unavailable'}</p></div></div><div className="relative flex gap-3"><span className="mt-1.5 grid h-6 w-6 place-items-center rounded-full border-2 border-emerald-400 bg-[#101820]"><MapPin size={12} className="text-emerald-300" /></span><div className="min-w-0"><p className="text-[10px] uppercase tracking-wider font-semibold text-gray-500">Destination</p><p className="mt-0.5 text-sm font-medium text-white break-words">{destination || 'Destination unavailable'}</p></div></div></div>;
}

export function EmptyState({ icon: Icon = MapPin, title, detail, action }) {
  return <div className="card p-12 text-center"><div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl border border-[#1E293B] bg-[#101820] text-gray-500"><Icon size={25} /></div><h3 className="text-lg font-bold text-white">{title}</h3><p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-gray-400">{detail}</p>{action && <div className="mt-6">{action}</div>}</div>;
}
