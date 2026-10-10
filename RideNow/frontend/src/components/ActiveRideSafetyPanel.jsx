import { useState, useEffect } from 'react';
import { Shield, ShieldAlert, Share2, AlertTriangle, Check, Copy, ExternalLink, Loader2, X } from 'lucide-react';
import toast from 'react-hot-toast';
import safetyService from '../services/safetyService';

export const ActiveRideSafetyPanel = ({ ride, onStatusChange }) => {
  const [sosModalOpen, setSosModalOpen] = useState(false);
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [shareLoading, setShareLoading] = useState(false);
  const [activeEvents, setActiveEvents] = useState([]);
  const [isSosActive, setIsSosActive] = useState(false);
  const [shareLink, setShareLink] = useState('');
  const [copied, setCopied] = useState(false);

  const [safetyDetails, setSafetyDetails] = useState(null);

  // Poll safety events for ride
  const fetchSafetyStatus = async () => {
    if (!ride?.id) return;
    try {
      const [events, centerData] = await Promise.all([
        safetyService.getRideSafetyEvents(ride.id).catch(() => []),
        safetyService.getSafetyCenter().catch(() => null),
      ]);
      setActiveEvents(events);
      const sos = events.some(e => 
        (e.event_type === 'SOS_TRIGGERED' || e.event_type === 'PASSENGER_SOS' || e.event_type === 'UNIVERSAL_SOS') && 
        (e.status === 'ACTIVE' || e.status === 'OPEN')
      );
      setIsSosActive(sos);
      const sc = centerData?.safety_center || centerData;
      if (sc?.active_ride) {
        setSafetyDetails(sc.active_ride);
      }
    } catch {
      // quiet fallback
    }
  };

  useEffect(() => {
    fetchSafetyStatus();
    const interval = setInterval(fetchSafetyStatus, 7000);
    return () => clearInterval(interval);
  }, [ride?.id]);

  const handleTriggerSOS = async () => {
    setLoading(true);
    try {
      const res = await safetyService.triggerSOS(ride.id, {
        latitude: ride.pickup_latitude,
        longitude: ride.pickup_longitude,
        note: 'Passenger initiated emergency assistance from mobile dashboard.',
      });
      setIsSosActive(true);
      setSosModalOpen(false);
      toast.success(res.message || 'SOS activated. Emergency safety workflow initiated.');
      fetchSafetyStatus();
      if (onStatusChange) onStatusChange();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to trigger SOS.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateShareLink = async () => {
    setShareLoading(true);
    try {
      const res = await safetyService.createShareLink(ride.id);
      const fullUrl = `${window.location.origin}${res.share_url}`;
      setShareLink(fullUrl);
      setShareModalOpen(true);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create share link.');
    } finally {
      setShareLoading(false);
    }
  };

  const handleCopyLink = () => {
    if (!shareLink) return;
    navigator.clipboard.writeText(shareLink);
    setCopied(true);
    toast.success('Share link copied to clipboard!');
    setTimeout(() => setCopied(false), 2500);
  };

  const activeNotice = activeEvents.find(e => e.status === 'ACTIVE' && e.event_type !== 'SOS_TRIGGERED');

  return (
    <div className="card p-5 border border-[#1E293B] bg-[#0A0F14] rounded-2xl shadow-lg transition-all duration-300">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${
            isSosActive ? 'bg-red-500/10 text-red-400 border border-red-500/30 animate-pulse' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
          }`}>
            {isSosActive ? <ShieldAlert size={18} /> : <Shield size={18} />}
          </div>
          <div>
            <h3 className="text-xs font-bold text-[#F5F7FA] uppercase tracking-wider">RideNow Safety Guard</h3>
            <p className="text-[11px] text-gray-400 flex items-center gap-1.5 mt-0.5">
              <span className={`w-1.5 h-1.5 rounded-full ${isSosActive ? 'bg-red-400 animate-ping' : 'bg-emerald-400'}`} />
              {isSosActive ? 'CRITICAL SOS ACTIVE' : activeNotice ? 'Route Deviation Monitored' : 'Corridor Monitored 24/7'}
            </p>
          </div>
        </div>

        <span className={`text-[10px] font-mono uppercase px-2.5 py-1 rounded-full border ${
          isSosActive
            ? 'bg-red-500/10 text-red-400 border-red-500/30 font-bold'
            : activeNotice
            ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
            : 'bg-[#101820] text-emerald-400 border-emerald-500/20'
        }`}>
          {isSosActive ? 'EMERGENCY' : activeNotice ? 'NOTICE' : 'PROTECTED'}
        </span>
      </div>

      {/* Notice Banner if active warning */}
      {activeNotice && !isSosActive && (
        <div className="mb-4 p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl text-xs text-amber-300 flex items-start gap-2.5">
          <AlertTriangle size={15} className="shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-amber-200">Route Notice Detected</p>
            <p className="text-[11px] text-amber-400/90 mt-0.5">
              Trip deviated from planned route. Safety engine is tracking progress.
            </p>
          </div>
        </div>
      )}

      {/* Emergency Active State */}
      {isSosActive && (
        <div className="mb-4 p-3.5 bg-red-950/40 border border-red-500/40 rounded-xl text-xs text-red-200 flex flex-col gap-2">
          <div className="flex items-center gap-2 text-red-300 font-bold">
            <ShieldAlert size={16} />
            <span>Emergency Safety Protocol Active</span>
          </div>
          <p className="text-[11px] text-gray-300">
            Designated safety workflow has been activated for this ride. Emergency contacts and telemetry logs are updated.
          </p>
        </div>
      )}

      {/* Vehicle Verification Badge if available */}
      {safetyDetails && (safetyDetails.vehicle_model || safetyDetails.driver_name) && (
        <div className="mb-4 p-2.5 bg-[#101820] border border-[#1E293B] rounded-xl text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono uppercase text-gray-500">Verified Ride:</span>
            <span className="font-semibold text-gray-200">{safetyDetails.driver_name || 'Assigned Driver'}</span>
            <span className="text-gray-400 font-mono">({safetyDetails.vehicle_model || 'Vehicle'} {safetyDetails.vehicle_number || ''})</span>
          </div>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">VERIFIED</span>
        </div>
      )}

      {/* Action Buttons */}
      <div className="grid grid-cols-2 gap-3 pt-2">
        <button
          type="button"
          onClick={handleCreateShareLink}
          disabled={shareLoading}
          className="flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl bg-[#101820] hover:bg-[#1A232E] border border-[#1E293B] text-gray-300 hover:text-white text-xs font-semibold tracking-wide transition-colors"
        >
          {shareLoading ? <Loader2 size={14} className="animate-spin text-[#38BDF8]" /> : <Share2 size={14} className="text-[#38BDF8]" />}
          Share Trip
        </button>

        <button
          type="button"
          onClick={() => setSosModalOpen(true)}
          className={`flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl text-xs font-bold tracking-wide transition-all ${
            isSosActive
              ? 'bg-red-500 text-white shadow-[0_0_15px_rgba(239,68,68,0.4)]'
              : 'bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30'
          }`}
        >
          <AlertTriangle size={14} />
          {isSosActive ? 'SOS Active' : 'Emergency / SOS'}
        </button>
      </div>

      {/* SOS Confirmation Modal */}
      {sosModalOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade-in">
          <div className="card max-w-md w-full p-6 bg-[#0A0F14] border border-red-500/40 rounded-2xl shadow-2xl relative">
            <button
              onClick={() => setSosModalOpen(false)}
              className="absolute top-4 right-4 text-gray-400 hover:text-white transition-colors"
            >
              <X size={18} />
            </button>

            <div className="w-12 h-12 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-400 flex items-center justify-center mb-4">
              <ShieldAlert size={24} />
            </div>

            <h3 className="text-lg font-bold text-[#F5F7FA] mb-2">Trigger Emergency Assistance?</h3>
            <p className="text-xs text-gray-400 leading-relaxed mb-4">
              This will record a critical safety event with live GPS coordinates and notify the RideNow safety team.
            </p>
            <div className="p-3 bg-red-950/40 border border-red-500/30 rounded-xl text-xs text-red-300 mb-6">
              <p className="font-bold">⚠️ Emergency Boundary Disclaimer:</p>
              <p className="text-[11px] text-red-400/90 mt-1">
                RideNow cannot contact police or ambulance directly. For emergency response, please dial <strong>112</strong> immediately.
              </p>
            </div>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setSosModalOpen(false)}
                className="flex-1 py-3 rounded-xl bg-[#101820] hover:bg-[#1A232E] border border-[#1E293B] text-gray-300 text-xs font-bold uppercase tracking-wider transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleTriggerSOS}
                disabled={loading}
                className="flex-1 py-3 rounded-xl bg-red-600 hover:bg-red-500 text-white text-xs font-bold uppercase tracking-wider transition-colors shadow-[0_0_20px_rgba(239,68,68,0.4)] flex items-center justify-center gap-2"
              >
                {loading ? <Loader2 size={16} className="animate-spin" /> : 'Confirm Trigger SOS'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Share Trip Link Modal */}
      {shareModalOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade-in">
          <div className="card max-w-md w-full p-6 bg-[#0A0F14] border border-[#1E293B] rounded-2xl shadow-2xl relative">
            <button
              onClick={() => setShareModalOpen(false)}
              className="absolute top-4 right-4 text-gray-400 hover:text-white transition-colors"
            >
              <X size={18} />
            </button>

            <div className="w-12 h-12 rounded-2xl bg-[#38BDF8]/10 border border-[#38BDF8]/30 text-[#38BDF8] flex items-center justify-center mb-4">
              <Share2 size={24} />
            </div>

            <h3 className="text-lg font-bold text-[#F5F7FA] mb-1">Share Live Trip Status</h3>
            <p className="text-xs text-gray-400 mb-4 leading-relaxed">
              Anyone with this link can view your live route, driver info, and safety status without requiring login credentials. Expires in 24 hours.
            </p>

            <div className="flex items-center gap-2 bg-[#101820] border border-[#1E293B] p-2.5 rounded-xl mb-5">
              <input
                type="text"
                readOnly
                value={shareLink}
                className="bg-transparent text-xs text-gray-300 flex-1 outline-none font-mono"
              />
              <button
                type="button"
                onClick={handleCopyLink}
                className="p-2 bg-[#1E293B] hover:bg-[#283548] text-[#38BDF8] rounded-lg transition-colors flex items-center gap-1 text-xs font-bold"
              >
                {copied ? <Check size={14} /> : <Copy size={14} />}
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>

            <button
              type="button"
              onClick={() => setShareModalOpen(false)}
              className="w-full py-3 rounded-xl bg-[#101820] hover:bg-[#1A232E] border border-[#1E293B] text-gray-300 text-xs font-bold uppercase tracking-wider transition-colors"
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default ActiveRideSafetyPanel;
