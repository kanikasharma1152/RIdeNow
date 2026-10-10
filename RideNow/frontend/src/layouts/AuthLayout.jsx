import { Outlet, Link } from 'react-router-dom';
import { Car, Sparkles, Shield, Navigation } from 'lucide-react';

const AuthLayout = () => {
  return (
    <div className="min-h-screen bg-[#05070A] text-[#F5F7FA] flex flex-col md:flex-row select-none">
      {/* Left side: Branding / Visuals (Hidden on Mobile) */}
      <div className="hidden md:flex md:w-1/2 bg-gradient-to-br from-[#080E15] via-[#0A121C] to-[#05070A] text-white flex-col justify-between p-12 lg:p-20 relative overflow-hidden border-r border-[#1E293B]">
        {/* Background glow and subtle mesh lines */}
        <div className="absolute top-0 right-0 -mr-20 -mt-20 w-96 h-96 rounded-full bg-[#38BDF8]/10 blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-80 h-80 rounded-full bg-[#0EA5E9]/10 blur-3xl pointer-events-none" />

        {/* Brand header */}
        <div className="relative z-10">
          <div className="flex items-center gap-3 text-2xl font-bold tracking-tight mb-8">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#38BDF8] to-[#0EA5E9] text-[#05070A] flex items-center justify-center shadow-[0_0_20px_rgba(56,189,248,0.4)]">
              <Car size={22} />
            </div>
            <span className="text-[#F5F7FA]">Ride<span className="text-[#38BDF8]">Now</span></span>
            <span className="text-[10px] font-mono font-semibold uppercase tracking-widest px-2 py-0.5 rounded-full bg-[#38BDF8]/10 text-[#38BDF8] border border-[#38BDF8]/30 ml-1">
              AI Core
            </span>
          </div>

          <h1 className="text-4xl lg:text-5xl font-bold leading-tight mb-5 tracking-tight text-[#F5F7FA]">
            The next generation of <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#38BDF8] via-[#7DD3FC] to-white">
              intelligent mobility.
            </span>
          </h1>
          <p className="text-base text-gray-400 max-w-md leading-relaxed">
            AI-orchestrated dispatch, multimodal visual navigation, real-time telemetry, and instant voice assistance.
          </p>

          {/* Key capability highlights */}
          <div className="grid grid-cols-2 gap-4 mt-8 max-w-md">
            <div className="p-3.5 rounded-xl bg-[#0D141B] border border-[#1E293B]">
              <div className="flex items-center gap-2 text-[#38BDF8] text-xs font-semibold mb-1">
                <Sparkles size={14} />
                Nova Assistant
              </div>
              <p className="text-[11px] text-gray-400">Natural language booking & fare transparency</p>
            </div>
            <div className="p-3.5 rounded-xl bg-[#0D141B] border border-[#1E293B]">
              <div className="flex items-center gap-2 text-emerald-400 text-xs font-semibold mb-1">
                <Shield size={14} />
                Safety Shield
              </div>
              <p className="text-[11px] text-gray-400">Deviation alerts & trusted trip sharing</p>
            </div>
          </div>
        </div>

        {/* Live quote / metrics */}
        <div className="relative z-10 pt-8 border-t border-[#1E293B]/60 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#101820] border border-[#1E293B] flex items-center justify-center text-[#38BDF8]">
              <Navigation size={18} />
            </div>
            <div>
              <p className="text-xs font-semibold text-[#F5F7FA]">Multimodal Mobility Command</p>
              <p className="text-[11px] text-gray-500">Live WebSockets · OSRM Routing · Neural Voice</p>
            </div>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#101820] border border-[#1E293B] text-[11px] text-emerald-400 font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            99.9% Uptime
          </div>
        </div>
      </div>

      {/* Right side: Auth Form */}
      <div className="w-full md:w-1/2 flex items-center justify-center p-6 sm:p-12 bg-[#05070A] relative">
        <div className="w-full max-w-md">
          {/* Mobile branding only shown on small screens */}
          <div className="md:hidden flex items-center justify-center gap-3 text-2xl font-bold tracking-tight mb-8 text-[#F5F7FA]">
            <div className="w-10 h-10 bg-gradient-to-tr from-[#38BDF8] to-[#0EA5E9] text-[#05070A] flex items-center justify-center rounded-xl shadow-md">
              <Car size={22} />
            </div>
            <span>Ride<span className="text-[#38BDF8]">Now</span></span>
          </div>

          <Outlet />
        </div>
      </div>
    </div>
  );
};

export default AuthLayout;
