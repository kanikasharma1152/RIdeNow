import { useState, useEffect } from 'react';
import { getNotifications, markNotificationRead, markAllNotificationsRead } from '../services/notificationService';
import { 
  Bell, 
  Car, 
  CreditCard, 
  Info, 
  Clock, 
  CheckCircle, 
  Loader2, 
  Radio, 
  Check, 
  Sparkles,
  ShieldAlert,
  Inbox
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import toast from 'react-hot-toast';

const getCategoryMeta = (type) => {
  const t = (type || '').toLowerCase();
  if (t.includes('ride') || t.includes('assign') || t.includes('match')) {
    return {
      icon: Car,
      color: 'text-[#38BDF8] bg-[#38BDF8]/10 border-[#38BDF8]/30',
      label: 'Ride Update',
      tagBg: 'bg-[#38BDF8]/10 text-[#38BDF8]'
    };
  }
  if (t.includes('pay') || t.includes('fare') || t.includes('earning')) {
    return {
      icon: CreditCard,
      color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
      label: 'Payment',
      tagBg: 'bg-emerald-500/10 text-emerald-400'
    };
  }
  if (t.includes('cancel') || t.includes('alert') || t.includes('urgent')) {
    return {
      icon: ShieldAlert,
      color: 'text-red-400 bg-red-500/10 border-red-500/30',
      label: 'Security & Alert',
      tagBg: 'bg-red-500/10 text-red-400'
    };
  }
  return {
    icon: Info,
    color: 'text-gray-400 bg-gray-500/10 border-gray-500/20',
    label: 'System Broadcast',
    tagBg: 'bg-gray-500/10 text-gray-400'
  };
};

const Notifications = () => {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState('all'); // 'all' | 'unread' | 'rides' | 'payments'

  const fetchNotifications = async () => {
    try {
      const data = await getNotifications();
      const rawList = Array.isArray(data) ? data : [];
      const seenIds = new Set();
      const seenRideTitles = new Set();
      const deduped = rawList.filter((n) => {
        if (!n) return false;
        if (n.id) {
          if (seenIds.has(n.id)) return false;
          seenIds.add(n.id);
        }
        if (n.ride_id && n.title) {
          const key = `${n.ride_id}:${n.title.toLowerCase()}`;
          if (seenRideTitles.has(key)) return false;
          seenRideTitles.add(key);
        }
        return true;
      });
      setNotifications(deduped);
    } catch (err) {
      toast.error('Failed to load notifications');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotifications();
  }, []);

  const handleMarkRead = async (id) => {
    try {
      await markNotificationRead(id);
      setNotifications(prev =>
        prev.map(n => n.id === id ? { ...n, is_read: true } : n)
      );
    } catch (err) {
      toast.error('Failed to mark notification as read');
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await markAllNotificationsRead();
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
      toast.success('All notifications marked as read');
    } catch (err) {
      toast.error('Failed to mark all as read');
    }
  };

  const unreadCount = notifications.filter(n => !n.is_read).length;

  // Filter items
  const filteredNotifications = notifications.filter(n => {
    if (activeFilter === 'unread') return !n.is_read;
    if (activeFilter === 'rides') {
      const t = (n.notification_type || n.type || '').toLowerCase();
      return t.includes('ride') || t.includes('driver') || t.includes('match');
    }
    if (activeFilter === 'payments') {
      const t = (n.notification_type || n.type || '').toLowerCase();
      return t.includes('pay') || t.includes('fare');
    }
    return true;
  });

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in pb-16">
      
      {/* 1. Header / Hero Card */}
      <div className="card-panel p-6 lg:p-8 bg-gradient-to-r from-[#0A0F14] via-[#101820] to-[#0A0F14] border border-[#1E293B] flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#38BDF8]/10 border border-[#38BDF8]/30 text-[#38BDF8] text-xs font-semibold uppercase tracking-wider mb-2.5">
            <Radio className="w-3.5 h-3.5 animate-pulse" />
            <span>Live Dispatch Telemetry</span>
          </div>
          <h1 className="text-2xl lg:text-3xl font-bold text-white tracking-tight">Notifications & Alerts</h1>
          <p className="text-gray-400 text-sm mt-1">
            Real-time fleet events, ride matching notifications, and payment receipts.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {unreadCount > 0 && (
            <button
              onClick={handleMarkAllRead}
              className="btn btn-secondary px-4 py-2.5 text-xs font-semibold flex items-center gap-2 rounded-xl"
            >
              <CheckCircle size={15} className="text-[#38BDF8]" />
              <span>Mark all read ({unreadCount})</span>
            </button>
          )}
        </div>
      </div>

      {/* 2. Filter Tabs & Metric Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
          {[
            { id: 'all', label: 'All Alerts', count: notifications.length },
            { id: 'unread', label: 'Unread', count: unreadCount },
            { id: 'rides', label: 'Rides', count: null },
            { id: 'payments', label: 'Payments', count: null },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveFilter(tab.id)}
              className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all shrink-0 flex items-center gap-2 ${
                activeFilter === tab.id
                  ? 'bg-[#38BDF8] text-[#05070A] shadow-[0_0_15px_rgba(56,189,248,0.3)]'
                  : 'bg-[#0A0F14] border border-[#1E293B] text-gray-400 hover:text-white hover:border-[#38BDF8]/40'
              }`}
            >
              <span>{tab.label}</span>
              {tab.count !== null && (
                <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                  activeFilter === tab.id ? 'bg-[#05070A] text-[#38BDF8]' : 'bg-[#101820] text-gray-400'
                }`}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>

        <div className="text-xs text-gray-500 font-mono">
          Showing {filteredNotifications.length} of {notifications.length} alerts
        </div>
      </div>

      {/* 3. Notification Cards List */}
      {loading ? (
        <div className="p-16 card flex flex-col items-center justify-center text-center">
          <Loader2 className="w-8 h-8 animate-spin text-[#38BDF8] mb-3" />
          <span className="text-xs font-mono text-gray-400">Querying telemetry broadcast relays...</span>
        </div>
      ) : filteredNotifications.length === 0 ? (
        <div className="card p-16 text-center flex flex-col items-center justify-center bg-[#0A0F14]">
          <div className="w-16 h-16 bg-[#101820] border border-[#1E293B] rounded-2xl flex items-center justify-center text-gray-600 mb-4 shadow-sm">
            <Inbox size={28} />
          </div>
          <h3 className="text-lg font-bold text-white mb-1">Queue Clear</h3>
          <p className="text-gray-400 text-xs max-w-sm">
            {activeFilter === 'unread' 
              ? 'All notifications have been acknowledged.' 
              : 'You are completely up to date with trip and telemetry events.'}
          </p>
        </div>
      ) : (
        <div className="space-y-3.5">
          {filteredNotifications.map((notif) => {
            const meta = getCategoryMeta(notif.notification_type || notif.type);
            const IconComponent = meta.icon;

            return (
              <div
                key={notif.id}
                onClick={() => !notif.is_read && handleMarkRead(notif.id)}
                className={`p-5 rounded-2xl border transition-all duration-200 relative group cursor-pointer ${
                  !notif.is_read
                    ? 'bg-[#101820] border-[#38BDF8]/40 shadow-[0_4px_20px_rgba(0,0,0,0.4)] hover:border-[#38BDF8]'
                    : 'bg-[#0A0F14] border-[#1E293B] hover:border-gray-700 opacity-80 hover:opacity-100'
                }`}
              >
                <div className="flex items-start gap-4">
                  {/* Category Icon Badge */}
                  <div className={`w-11 h-11 rounded-xl border flex items-center justify-center shrink-0 mt-0.5 ${meta.color}`}>
                    <IconComponent size={20} />
                  </div>

                  {/* Main Content Area */}
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] font-mono uppercase font-bold px-2 py-0.5 rounded-md ${meta.tagBg}`}>
                          {meta.label}
                        </span>
                        <h3 className={`text-sm font-semibold tracking-tight ${!notif.is_read ? 'text-white' : 'text-gray-300'}`}>
                          {notif.title}
                        </h3>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        {!notif.is_read && (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#38BDF8] bg-[#38BDF8]/10 border border-[#38BDF8]/30 px-2 py-0.5 rounded-full">
                            <span className="w-1.5 h-1.5 rounded-full bg-[#38BDF8] animate-ping" />
                            New
                          </span>
                        )}
                        <span className="text-[11px] text-gray-500 font-mono flex items-center gap-1">
                          <Clock size={11} />
                          {formatDistanceToNow(new Date(notif.created_at), { addSuffix: true })}
                        </span>
                      </div>
                    </div>

                    <p className="text-xs text-gray-300 leading-relaxed mt-1.5">
                      {notif.message}
                    </p>

                    {/* Quick acknowledgement action on hover */}
                    {!notif.is_read && (
                      <div className="mt-3 flex items-center gap-2 pt-2 border-t border-[#1E293B]/60">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleMarkRead(notif.id);
                          }}
                          className="text-[11px] font-medium text-[#38BDF8] hover:underline flex items-center gap-1"
                        >
                          <Check size={12} /> Acknowledge alert
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default Notifications;

