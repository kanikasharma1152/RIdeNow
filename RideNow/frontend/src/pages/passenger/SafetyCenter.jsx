import { useState, useEffect, useCallback } from 'react';
import {
  Shield,
  ShieldCheck,
  ShieldAlert,
  Users,
  UserPlus,
  Trash2,
  Share2,
  History,
  AlertTriangle,
  Loader2,
  Plus,
  X,
  Car,
  MapPin,
  Copy,
  CheckCircle2,
  Clock,
  Zap,
  Eye,
  Phone,
} from 'lucide-react';
import toast from 'react-hot-toast';
import safetyService from '../../services/safetyService';

const SEV_COLOR = {
  CRITICAL: 'text-red-400 bg-red-500/10 border-red-500/30',
  HIGH: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
  MEDIUM: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  LOW: 'text-[#38BDF8] bg-[#38BDF8]/10 border-[#38BDF8]/30',
  INFO: 'text-gray-400 bg-gray-500/10 border-gray-500/20',
};

const SafetyCenter = () => {
  const [safetyCenter, setSafetyCenter] = useState(null);
  const [contacts, setContacts] = useState([]);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [sosLoading, setSosLoading] = useState(false);
  const [shareLoading, setShareLoading] = useState(false);
  const [shareResult, setShareResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [copied, setCopied] = useState(false);
  const [newContact, setNewContact] = useState({
    name: '',
    phone: '',
    relationship: 'Family',
  });

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [centerData, contactsData, eventsData] = await Promise.all([
        safetyService.getSafetyCenter().catch(() => null),
        safetyService.getTrustedContacts().catch(() => []),
        safetyService.getActiveEvents().catch(() => []),
      ]);
      setSafetyCenter(centerData?.safety_center || centerData);
      setContacts(Array.isArray(contactsData) ? contactsData : []);
      setEvents(Array.isArray(eventsData) ? eventsData : []);
    } catch {
      toast.error('Could not load safety information.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSOS = async () => {
    if (!window.confirm('⚠️ Trigger Emergency SOS? This will alert the RideNow safety team. For police/ambulance, call 112 directly.')) return;
    setSosLoading(true);
    try {
      const data = await safetyService.triggerUniversalSOS();
      const sos = data?.sos || data;
      toast.success(`🆘 SOS Event #${sos?.event_id || sos?.id || 'logged'} activated. Safety team alerted.`, { duration: 6000 });
      toast('⚠️ RideNow cannot contact police/ambulance. Call 112 for emergency services.', {
        icon: '📞',
        duration: 8000,
        style: { background: '#1a0000', color: '#fca5a5', border: '1px solid #7f1d1d' },
      });
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'SOS trigger failed. Call 112 directly.');
    } finally {
      setSosLoading(false);
    }
  };

  const handleShareRide = async () => {
    const activeRide = safetyCenter?.active_ride;
    if (!activeRide?.ride_id) {
      toast.error('No active ride to share right now.');
      return;
    }
    setShareLoading(true);
    try {
      const data = await safetyService.createShareLink(activeRide.ride_id);
      setShareResult(data?.share || data);
      toast.success('Ride share link generated!');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Could not generate share link.');
    } finally {
      setShareLoading(false);
    }
  };

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success('Link copied to clipboard!');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('Could not copy. Please copy manually.');
    }
  };

  const handleAddContact = async (e) => {
    e.preventDefault();
    if (!newContact.name.trim() || !newContact.phone.trim()) {
      toast.error('Please enter name and phone number.');
      return;
    }
    setSubmitting(true);
    try {
      await safetyService.addTrustedContact(newContact);
      toast.success('Trusted contact added.');
      setNewContact({ name: '', phone: '', relationship: 'Family' });
      setAddModalOpen(false);
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to add contact.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteContact = async (contactId) => {
    if (!window.confirm('Remove this trusted contact?')) return;
    try {
      await safetyService.deleteTrustedContact(contactId);
      toast.success('Contact removed.');
      setContacts((prev) => prev.filter((c) => c.id !== contactId));
    } catch {
      toast.error('Failed to remove contact.');
    }
  };

  if (loading) {
    return (
      <div className="flex h-[75vh] items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-[#38BDF8]" />
      </div>
    );
  }

  const activeRide = safetyCenter?.active_ride;
  const routeDeviation = safetyCenter?.route_deviation;
  const isDeviated = routeDeviation?.is_deviated;

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-fade-in pb-20">

      {/* Header */}
      <div className="card p-6 md:p-8 bg-[#0A0F14] border border-[#1E293B] rounded-2xl shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 bottom-0 w-1/3 bg-gradient-to-l from-[#38BDF8]/5 to-transparent pointer-events-none" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#101820] border border-[#38BDF8]/30 text-[#38BDF8] text-xs font-mono mb-3">
              <ShieldCheck size={14} />
              RideNow Safety Intelligence — Phase 13
            </div>
            <h1 className="text-2xl md:text-3xl font-bold text-[#F5F7FA]">Safety Command Center</h1>
            <p className="text-sm text-gray-400 mt-1 max-w-xl">
              AI-powered safety monitoring, route deviation detection, emergency SOS, and trusted ride sharing.
            </p>
          </div>
          <div className="flex items-center gap-3 bg-[#101820] p-4 rounded-xl border border-[#1E293B]">
            <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0">
              <ShieldCheck size={20} />
            </div>
            <div>
              <p className="text-xs text-gray-400 font-mono uppercase">Safety Shield</p>
              <p className="text-sm font-bold text-emerald-400">ACTIVE &amp; READY</p>
            </div>
          </div>
        </div>
      </div>

      {/* Route Deviation Alert */}
      {isDeviated && (
        <div className="card p-4 bg-red-900/20 border border-red-500/40 rounded-2xl flex items-start gap-3">
          <AlertTriangle className="text-red-400 shrink-0 mt-0.5" size={20} />
          <div>
            <p className="text-sm font-bold text-red-300">⚠️ Route Deviation Detected</p>
            <p className="text-xs text-red-400 mt-0.5">
              Your vehicle is {routeDeviation?.deviation_meters || 0}m off the expected route.
              If you feel unsafe, trigger SOS or call <strong>112</strong> immediately.
            </p>
          </div>
        </div>
      )}

      {/* Active Ride Panel */}
      {activeRide && (
        <div className="card p-5 bg-[#0A0F14] border border-[#38BDF8]/30 rounded-2xl shadow-lg">
          <div className="flex items-center gap-2 mb-4">
            <Car size={18} className="text-[#38BDF8]" />
            <h2 className="text-base font-bold text-[#F5F7FA]">Active Ride</h2>
            <span className="ml-auto text-xs font-mono px-2 py-0.5 rounded bg-[#38BDF8]/10 text-[#38BDF8] border border-[#38BDF8]/30">
              #{activeRide.ride_id}
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <div className="bg-[#101820] rounded-xl p-3 border border-[#1E293B]">
              <p className="text-[10px] text-gray-500 font-mono uppercase">Driver</p>
              <p className="text-xs font-bold text-[#F5F7FA] mt-0.5">{activeRide.driver_name || 'Assigned'}</p>
            </div>
            <div className="bg-[#101820] rounded-xl p-3 border border-[#1E293B]">
              <p className="text-[10px] text-gray-500 font-mono uppercase">Vehicle</p>
              <p className="text-xs font-bold text-[#F5F7FA] mt-0.5">{activeRide.vehicle_model || 'N/A'}</p>
            </div>
            <div className="bg-[#101820] rounded-xl p-3 border border-[#1E293B]">
              <p className="text-[10px] text-gray-500 font-mono uppercase">Plate</p>
              <p className="text-xs font-bold text-[#F5F7FA] font-mono mt-0.5">{activeRide.vehicle_number || 'N/A'}</p>
            </div>
            <div className="bg-[#101820] rounded-xl p-3 border border-[#1E293B]">
              <p className="text-[10px] text-gray-500 font-mono uppercase">Status</p>
              <p className="text-xs font-bold text-emerald-400 mt-0.5">{activeRide.status || 'Active'}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleShareRide}
              disabled={shareLoading}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 text-xs font-semibold transition-colors"
            >
              {shareLoading ? <Loader2 size={13} className="animate-spin" /> : <Share2 size={13} />}
              Share Ride
            </button>
            <button
              onClick={handleSOS}
              disabled={sosLoading}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-400 text-xs font-semibold transition-colors"
            >
              {sosLoading ? <Loader2 size={13} className="animate-spin" /> : <Zap size={13} />}
              SOS
            </button>
          </div>
        </div>
      )}

      {/* No Active Ride SOS Panel */}
      {!activeRide && (
        <div className="card p-5 bg-[#0A0F14] border border-red-500/20 rounded-2xl shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 text-red-400 text-xs font-bold uppercase tracking-wider mb-1">
                <ShieldAlert size={15} />
                Emergency SOS
              </div>
              <p className="text-xs text-gray-400 max-w-md">
                Trigger SOS anytime — even without an active ride. This logs a critical safety event and notifies the RideNow safety team.
              </p>
              <p className="text-[11px] text-red-400/70 mt-1">
                ⚠️ RideNow cannot contact police or ambulance. Call <strong>112</strong> for emergency services.
              </p>
            </div>
            <button
              onClick={handleSOS}
              disabled={sosLoading}
              className="ml-4 px-5 py-3 rounded-xl bg-red-600 hover:bg-red-700 text-white text-sm font-bold transition-colors flex items-center gap-2 shrink-0 shadow-lg shadow-red-900/30"
            >
              {sosLoading ? <Loader2 size={15} className="animate-spin" /> : <Zap size={15} />}
              SOS
            </button>
          </div>
        </div>
      )}

      {/* Share Result Panel */}
      {shareResult && (
        <div className="card p-5 bg-[#0A0F14] border border-amber-500/30 rounded-2xl shadow-lg">
          <div className="flex items-center gap-2 mb-3">
            <Share2 size={16} className="text-amber-400" />
            <h3 className="text-sm font-bold text-[#F5F7FA]">Ride Share Link</h3>
            <button onClick={() => setShareResult(null)} className="ml-auto text-gray-500 hover:text-white">
              <X size={14} />
            </button>
          </div>
          <p className="text-xs text-gray-400 mb-3">
            {shareResult.message || 'Copy and share this link manually — it has NOT been sent automatically.'}
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-[11px] font-mono text-amber-300 bg-[#101820] px-3 py-2 rounded-xl border border-[#1E293B] overflow-x-auto">
              {shareResult.share_url || shareResult.url || 'Link not available'}
            </code>
            <button
              onClick={() => copyToClipboard(shareResult.share_url || shareResult.url || '')}
              className="p-2.5 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 transition-colors"
            >
              {copied ? <CheckCircle2 size={15} /> : <Copy size={15} />}
            </button>
          </div>
          {shareResult.share_text && (
            <p className="text-[11px] text-gray-500 mt-2">{shareResult.share_text}</p>
          )}
        </div>
      )}

      {/* Active Events Banner */}
      {events.length > 0 && (
        <div className="card p-4 bg-amber-900/10 border border-amber-500/30 rounded-2xl">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle size={16} className="text-amber-400" />
            <h3 className="text-sm font-bold text-amber-300">Active Safety Events</h3>
            <span className="ml-auto text-xs font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400">{events.length}</span>
          </div>
          <div className="space-y-2">
            {events.slice(0, 3).map((ev) => (
              <div key={ev.id} className={`flex items-center justify-between p-3 rounded-xl border text-xs ${SEV_COLOR[ev.severity] || SEV_COLOR.INFO}`}>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${
                    ev.severity === 'CRITICAL' ? 'bg-red-400' : ev.severity === 'HIGH' ? 'bg-amber-400' : 'bg-[#38BDF8]'
                  }`} />
                  <span className="font-semibold uppercase tracking-wide text-[11px]">{ev.event_type?.replace(/_/g, ' ')}</span>
                </div>
                <span className="font-mono text-[10px] uppercase">{ev.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* Trusted Contacts */}
        <div className="lg:col-span-7 space-y-6">
          <div className="card p-6 bg-[#0A0F14] border border-[#1E293B] rounded-2xl shadow-lg">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Users size={18} className="text-[#38BDF8]" />
                <h2 className="text-base font-bold text-[#F5F7FA]">Trusted Contacts</h2>
                <span className="text-xs font-mono text-gray-500">({contacts.length})</span>
              </div>
              <button
                type="button"
                onClick={() => setAddModalOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#38BDF8]/10 hover:bg-[#38BDF8]/20 border border-[#38BDF8]/30 text-[#38BDF8] text-xs font-semibold transition-colors"
              >
                <Plus size={14} />
                Add Contact
              </button>
            </div>
            <p className="text-xs text-gray-400 mb-5 leading-relaxed">
              Share your live ride link with these contacts during emergencies. RideNow does not auto-send messages — you must share the link manually.
            </p>
            {contacts.length === 0 ? (
              <div className="text-center py-8 border border-dashed border-[#1E293B] rounded-xl bg-[#101820]/50">
                <Users size={28} className="mx-auto text-gray-600 mb-2" />
                <p className="text-xs font-semibold text-gray-400">No trusted contacts yet</p>
                <p className="text-[11px] text-gray-500 mt-1">Add family or friends for emergency peace of mind.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {contacts.map((c) => (
                  <div key={c.id} className="flex items-center justify-between p-3.5 bg-[#101820] border border-[#1E293B] rounded-xl hover:border-gray-700 transition-colors">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-[#F5F7FA]">{c.name}</span>
                        {c.relationship && (
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#1A232E] text-gray-400">{c.relationship}</span>
                        )}
                      </div>
                      <p className="text-xs text-gray-400 font-mono mt-0.5 flex items-center gap-1">
                        <Phone size={10} />
                        {c.phone}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleDeleteContact(c.id)}
                      className="p-2 text-gray-500 hover:text-red-400 transition-colors rounded-lg hover:bg-red-500/10"
                      title="Remove contact"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Safety Event History */}
          <div className="card p-6 bg-[#0A0F14] border border-[#1E293B] rounded-2xl shadow-lg">
            <div className="flex items-center gap-2 mb-4">
              <History size={18} className="text-[#38BDF8]" />
              <h2 className="text-base font-bold text-[#F5F7FA]">Safety Event History</h2>
            </div>
            {safetyCenter?.safety_events?.length === 0 || !safetyCenter?.safety_events ? (
              <p className="text-xs text-gray-500 py-4 text-center">No safety events recorded. All your journeys are clear. ✓</p>
            ) : (
              <div className="space-y-2.5">
                {(safetyCenter.safety_events || []).slice(0, 8).map((e) => (
                  <div key={e.id} className="flex items-center justify-between p-3 bg-[#101820] border border-[#1E293B] rounded-xl text-xs">
                    <div className="flex items-center gap-2.5">
                      <div className={`w-2 h-2 rounded-full ${
                        e.severity === 'CRITICAL' ? 'bg-red-400' : e.severity === 'HIGH' ? 'bg-amber-400' : 'bg-[#38BDF8]'
                      }`} />
                      <div>
                        <span className="font-semibold text-gray-200 uppercase tracking-wide text-[11px]">{e.event_type?.replace(/_/g, ' ')}</span>
                        <p className="text-[10px] text-gray-500 font-mono mt-0.5">
                          {e.ride_id ? `Ride #${e.ride_id} • ` : ''}{new Date(e.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#1A232E] text-gray-400 uppercase">{e.status}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: Protections + Emergency Info */}
        <div className="lg:col-span-5 space-y-4">
          <div className="card p-5 bg-[#0A0F14] border border-[#1E293B] rounded-2xl shadow-lg space-y-4">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">Automated Protections</h3>
            <div className="space-y-3">
              <div className="flex items-start gap-3 p-3 bg-[#101820] rounded-xl border border-[#1E293B]">
                <ShieldCheck size={18} className="text-[#38BDF8] shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-xs font-bold text-[#F5F7FA]">Corridor Deviation Shield</h4>
                  <p className="text-[11px] text-gray-400 mt-0.5">Real-time GPS comparison against OSRM routes detects abnormal diversions automatically.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-3 bg-[#101820] rounded-xl border border-[#1E293B]">
                <Clock size={18} className="text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-xs font-bold text-[#F5F7FA]">Prolonged Stop Detection</h4>
                  <p className="text-[11px] text-gray-400 mt-0.5">Vehicles stationary for &gt;5 minutes trigger proactive automated safety checks.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-3 bg-[#101820] rounded-xl border border-[#1E293B]">
                <Share2 size={18} className="text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-xs font-bold text-[#F5F7FA]">Expiring Tracking Links</h4>
                  <p className="text-[11px] text-gray-400 mt-0.5">Share live trip progress without exposing credentials. Links expire after ride completion.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-3 bg-[#101820] rounded-xl border border-[#1E293B]">
                <Eye size={18} className="text-purple-400 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-xs font-bold text-[#F5F7FA]">Vehicle Verification</h4>
                  <p className="text-[11px] text-gray-400 mt-0.5">View driver name, vehicle model, and plate number before boarding to verify your ride.</p>
                </div>
              </div>
            </div>
          </div>

          {/* Emergency Disclaimer */}
          <div className="card p-5 bg-[#0A0F14] border border-red-500/20 rounded-2xl shadow-lg">
            <div className="flex items-center gap-2 text-red-400 text-xs font-bold uppercase tracking-wider mb-3">
              <AlertTriangle size={15} />
              Emergency Response Honest Limits
            </div>
            <div className="space-y-2 text-xs text-gray-400">
              <p>✓ RideNow can log safety events and alert the safety team.</p>
              <p>✓ RideNow can flag route deviations and prolonged stops.</p>
              <p>✓ RideNow can generate shareable ride tracking links.</p>
              <p className="text-red-400/80">✗ RideNow cannot contact police, ambulance, or fire services.</p>
              <p className="text-red-400/80">✗ RideNow cannot auto-send WhatsApp, SMS, or calls.</p>
              <p className="mt-3 font-semibold text-red-300">In life-threatening emergencies, call 112 directly.</p>
            </div>
          </div>

          {/* AI Safety Assistant Hint */}
          <div className="card p-5 bg-[#0A0F14] border border-[#38BDF8]/20 rounded-2xl shadow-lg">
            <div className="flex items-center gap-2 text-[#38BDF8] text-xs font-bold uppercase tracking-wider mb-2">
              <Shield size={15} />
              AI Safety Assistant
            </div>
            <p className="text-xs text-gray-400">
              Nova AI understands safety intent. Try saying:
            </p>
            <div className="mt-2 space-y-1.5">
              {['"I don\'t feel safe"', '"Share my ride"', '"What car is coming?"', '"Route deviation"', '"SOS"'].map((phrase) => (
                <div key={phrase} className="text-[11px] font-mono text-[#38BDF8]/70 bg-[#101820] px-3 py-1.5 rounded-lg border border-[#1E293B]">
                  {phrase}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Add Contact Modal */}
      {addModalOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade-in">
          <div className="card max-w-md w-full p-6 bg-[#0A0F14] border border-[#1E293B] rounded-2xl shadow-2xl relative">
            <button
              onClick={() => setAddModalOpen(false)}
              className="absolute top-4 right-4 text-gray-400 hover:text-white transition-colors"
            >
              <X size={18} />
            </button>
            <div className="w-10 h-10 rounded-xl bg-[#38BDF8]/10 border border-[#38BDF8]/30 text-[#38BDF8] flex items-center justify-center mb-3">
              <UserPlus size={20} />
            </div>
            <h3 className="text-lg font-bold text-[#F5F7FA] mb-1">Add Trusted Contact</h3>
            <p className="text-xs text-gray-400 mb-5">This person will receive your ride share link when you share your trip manually.</p>
            <form onSubmit={handleAddContact} className="space-y-4">
              <div>
                <label className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block mb-1.5">Full Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Priya Sharma"
                  value={newContact.name}
                  onChange={(e) => setNewContact({ ...newContact, name: e.target.value })}
                  className="w-full bg-[#101820] border border-[#1E293B] rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-[#38BDF8]"
                />
              </div>
              <div>
                <label className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block mb-1.5">Mobile Phone</label>
                <input
                  type="tel"
                  required
                  placeholder="+91 98765 43210"
                  value={newContact.phone}
                  onChange={(e) => setNewContact({ ...newContact, phone: e.target.value })}
                  className="w-full bg-[#101820] border border-[#1E293B] rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-[#38BDF8]"
                />
              </div>
              <div>
                <label className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block mb-1.5">Relationship</label>
                <select
                  value={newContact.relationship}
                  onChange={(e) => setNewContact({ ...newContact, relationship: e.target.value })}
                  className="w-full bg-[#101820] border border-[#1E293B] rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#38BDF8]"
                >
                  <option value="Family">Family</option>
                  <option value="Parent">Parent</option>
                  <option value="Spouse">Spouse</option>
                  <option value="Sibling">Sibling</option>
                  <option value="Friend">Friend</option>
                  <option value="Colleague">Colleague</option>
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setAddModalOpen(false)}
                  className="flex-1 py-2.5 rounded-xl bg-[#101820] hover:bg-[#1A232E] border border-[#1E293B] text-gray-300 text-xs font-bold transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-1 py-2.5 rounded-xl bg-[#38BDF8] hover:bg-[#38BDF8]/90 text-black text-xs font-bold transition-colors flex items-center justify-center gap-1.5"
                >
                  {submitting ? <Loader2 size={14} className="animate-spin" /> : 'Save Contact'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default SafetyCenter;
