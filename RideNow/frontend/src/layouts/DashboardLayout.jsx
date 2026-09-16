import { useState, useEffect } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { 
  Home, 
  MapPin, 
  Clock, 
  Bell, 
  User, 
  CreditCard, 
  LogOut, 
  Menu,
  X,
  Car,
  Sparkles,
  Compass,
  BarChart3,
  Bot
} from 'lucide-react';
import toast from 'react-hot-toast';
import notificationService from '../services/notificationService';
import ChatWidget from '../components/ChatWidget';

const DashboardLayout = () => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    // Fetch unread notifications count
    const fetchUnread = async () => {
      try {
        const data = await notificationService.getUnreadCount();
        setUnreadCount(data.count || 0);
      } catch (err) {
        console.error("Failed to fetch notifications", err);
      }
    };
    fetchUnread();
    
    // Poll every 30 seconds
    const interval = setInterval(fetchUnread, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleLogout = async () => {
    try {
      await logout();
      toast.success('Logged out successfully');
      navigate('/login');
    } catch (err) {
      toast.error('Failed to logout properly');
    }
  };

  let navItems = [];
  if (user?.role === 'admin') {
    navItems = [
      { name: 'Command Center', path: '/admin/dashboard', icon: BarChart3 },
      { name: 'AI Assistant', path: '/admin/assistant', icon: Sparkles },
      { name: 'Notifications', path: '/admin/notifications', icon: Bell, badge: unreadCount },
      { name: 'Profile', path: '/admin/profile', icon: User },
    ];
  } else if (user?.role === 'driver') {
    navItems = [
      { name: 'Driver Copilot', path: '/driver/dashboard', icon: Compass },
      { name: 'AI Copilot Chat', path: '/driver/copilot', icon: Bot },
      { name: 'Assigned Rides', path: '/driver/rides', icon: Clock },
      { name: 'Earnings', path: '/driver/earnings', icon: CreditCard },
      { name: 'Notifications', path: '/driver/notifications', icon: Bell, badge: unreadCount },
      { name: 'Driver Profile', path: '/driver/profile', icon: User },
    ];
  } else {
    // Passenger
    navItems = [
      { name: 'Dashboard', path: '/dashboard', icon: Home },
      { name: 'AI Assistant', path: '/assistant', icon: Sparkles },
      { name: 'Book Ride', path: '/book-ride', icon: MapPin },
      { name: 'My Rides', path: '/rides', icon: Clock },
      { name: 'Payments', path: '/payments', icon: CreditCard },
      { name: 'Notifications', path: '/notifications', icon: Bell, badge: unreadCount },
      { name: 'Profile', path: '/profile', icon: User },
    ];
  }

  // Helper to get current page title based on path
  const getPageTitle = () => {
    const item = navItems.find(item => 
      location.pathname === item.path || 
      (item.path !== '/dashboard' && item.path !== '/driver/dashboard' && item.path !== '/admin/dashboard' && location.pathname.startsWith(item.path + '/'))
    );
    if (item) return item.name;
    if (location.pathname.includes('/rides/')) return 'Ride Details';
    return 'RideNow Mobility';
  };

  return (
    <div className="min-h-screen bg-[#05070A] text-[#F5F7FA] flex flex-col md:flex-row font-sans">
      
      {/* 
        =================================
        DESKTOP COMMAND SIDEBAR
        =================================
      */}
      <aside className="hidden md:flex flex-col w-64 bg-[#0A0F14] border-r border-[#1E293B] fixed h-full z-20">
        {/* Brand Header */}
        <div className="h-20 flex items-center justify-between px-6 border-b border-[#1E293B]">
          <Link to="/" className="flex items-center gap-2.5 text-xl font-bold tracking-tight text-[#F5F7FA]">
            <div className="w-8 h-8 bg-[#38BDF8] text-[#05070A] flex items-center justify-center rounded-xl shadow-[0_0_15px_rgba(56,189,248,0.4)]">
              <Car size={18} strokeWidth={2.5} />
            </div>
            <span>Ride<span className="text-[#38BDF8]">Now</span></span>
          </Link>
          <span className="text-[10px] font-mono uppercase bg-[#101820] text-gray-400 border border-[#1E293B] px-2 py-0.5 rounded-md">
            v2.0 AI
          </span>
        </div>

        {/* AI System Status Banner */}
        <div className="mx-4 mt-5 p-3 rounded-xl bg-[#101820] border border-[#1E293B] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#38BDF8] opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#38BDF8]"></span>
            </span>
            <span className="text-xs font-mono font-semibold text-gray-300">AI SYSTEM</span>
          </div>
          <span className="text-[10px] font-mono text-[#38BDF8] bg-[#38BDF8]/10 border border-[#38BDF8]/30 px-2 py-0.5 rounded-full">
            ONLINE
          </span>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 py-6 px-4 space-y-1.5 overflow-y-auto no-scrollbar">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path || (
              item.path !== '/dashboard' && 
              item.path !== '/driver/dashboard' && 
              item.path !== '/admin/dashboard' && 
              location.pathname.startsWith(item.path + '/')
            );
            return (
              <Link
                key={item.name}
                to={item.path}
                className={`flex items-center gap-3 px-3.5 py-2.5 rounded-xl transition-all duration-200 ${
                  isActive 
                    ? 'bg-[#38BDF8] text-[#05070A] font-semibold shadow-[0_0_20px_rgba(56,189,248,0.3)]' 
                    : 'text-gray-400 hover:text-[#F5F7FA] hover:bg-[#101820]'
                }`}
              >
                <Icon size={18} className={isActive ? 'text-[#05070A]' : 'text-gray-400'} />
                <span className="text-sm">{item.name}</span>
                {item.badge > 0 && (
                  <span className={`ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded-full ${
                    isActive ? 'bg-[#05070A] text-[#38BDF8]' : 'bg-[#38BDF8] text-[#05070A]'
                  }`}>
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Logout */}
        <div className="p-4 border-t border-[#1E293B]">
          <button 
            onClick={handleLogout}
            className="flex w-full items-center gap-3 px-4 py-2.5 text-gray-400 hover:text-red-400 hover:bg-[#101820] rounded-xl transition-all text-sm font-medium"
          >
            <LogOut size={18} />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* 
        =================================
        MAIN CONTENT AREA
        =================================
      */}
      <div className="flex-1 md:ml-64 flex flex-col min-h-screen relative bg-[#05070A]">
        
        {/* TOP BAR */}
        <header className="h-16 md:h-20 bg-[#0A0F14]/90 backdrop-blur-md border-b border-[#1E293B] flex items-center justify-between px-4 md:px-8 z-10 sticky top-0">
          {/* Mobile Menu Button & Brand */}
          <div className="flex items-center gap-3 md:hidden">
            <button 
              onClick={() => setMobileMenuOpen(true)}
              className="p-2 -ml-2 text-gray-300 hover:bg-[#101820] rounded-lg"
            >
              <Menu size={22} />
            </button>
            <div className="flex items-center gap-2 font-bold text-base text-[#F5F7FA]">
              <div className="w-6 h-6 bg-[#38BDF8] text-[#05070A] rounded-lg flex items-center justify-center">
                <Car size={14} />
              </div>
              RideNow
            </div>
          </div>

          {/* Desktop Page Title */}
          <div className="hidden md:flex items-center gap-3">
            <h1 className="text-lg font-bold text-[#F5F7FA] tracking-wide">
              {getPageTitle()}
            </h1>
          </div>

          {/* User Profile & Action Strip */}
          <div className="flex items-center gap-4">
            {/* Live AI Assistant Quick Chip */}
            <Link
              to={user?.role === 'driver' ? '/driver/assistant' : user?.role === 'admin' ? '/admin/assistant' : '/assistant'}
              className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#101820] border border-[#1E293B] hover:border-[#38BDF8]/50 text-xs text-gray-300 hover:text-[#38BDF8] transition-colors"
            >
              <Sparkles size={14} className="text-[#38BDF8]" />
              <span className="font-mono">Command AI</span>
            </Link>

            {/* Notification Bell */}
            <Link 
              to={user?.role === 'driver' ? '/driver/notifications' : '/notifications'} 
              className="relative p-2 text-gray-400 hover:text-[#F5F7FA] hover:bg-[#101820] rounded-full transition-colors"
            >
              <Bell size={18} />
              {unreadCount > 0 && (
                <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-[#38BDF8] rounded-full shadow-[0_0_8px_#38BDF8]"></span>
              )}
            </Link>
            
            {/* Avatar & Info */}
            <Link 
              to={user?.role === 'driver' ? '/driver/profile' : '/profile'} 
              className="flex items-center gap-3 pl-3 md:border-l border-[#1E293B] hover:opacity-90 transition-opacity"
            >
              <div className="hidden md:block text-right">
                <p className="text-xs font-semibold text-[#F5F7FA] leading-tight">{user?.name}</p>
                <p className="text-[10px] text-[#38BDF8] font-mono capitalize">{user?.role}</p>
              </div>
              <div className="w-8 h-8 rounded-full bg-[#101820] border border-[#1E293B] text-[#38BDF8] flex items-center justify-center font-bold text-xs shadow-sm">
                {user?.name?.charAt(0) || 'U'}
              </div>
            </Link>
          </div>
        </header>

        {/* PAGE CONTENT */}
        <main className="flex-1 min-h-0 w-full max-w-7xl mx-auto overflow-y-auto p-4 pb-28 md:p-8 md:pb-16">
          <Outlet />
        </main>
      </div>

      {/* 
        =================================
        MOBILE BOTTOM NAVIGATION
        =================================
      */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-[#0A0F14] border-t border-[#1E293B] flex justify-around items-center h-16 z-30 pb-safe">
        {navItems.slice(0, 4).map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path || (
            item.path !== '/dashboard' && 
            item.path !== '/driver/dashboard' && 
            item.path !== '/admin/dashboard' && 
            location.pathname.startsWith(item.path + '/')
          );
          
          return (
            <Link 
              key={item.name} 
              to={item.path}
              className={`flex flex-col items-center justify-center w-full h-full space-y-1 relative ${
                isActive ? 'text-[#38BDF8]' : 'text-gray-400'
              }`}
            >
              <div className="relative">
                <Icon size={18} className={isActive ? 'stroke-[2.5px]' : ''} />
                {item.badge > 0 && (
                  <span className="absolute -top-1 -right-1.5 w-2 h-2 bg-[#38BDF8] rounded-full"></span>
                )}
              </div>
              <span className="text-[10px] font-medium tracking-tight">{item.name}</span>
            </Link>
          );
        })}
      </nav>

      {/* 
        =================================
        MOBILE SIDE MENU (Overlay)
        =================================
      */}
      {mobileMenuOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div 
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={() => setMobileMenuOpen(false)}
          ></div>
          <div className="relative w-72 bg-[#0A0F14] border-r border-[#1E293B] h-full flex flex-col shadow-2xl animate-in slide-in-from-left duration-300">
            <div className="p-4 border-b border-[#1E293B] flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#101820] border border-[#1E293B] text-[#38BDF8] flex items-center justify-center font-bold text-base">
                  {user?.name?.charAt(0) || 'U'}
                </div>
                <div>
                  <p className="font-semibold text-sm text-[#F5F7FA] leading-tight">{user?.name}</p>
                  <p className="text-[11px] text-[#38BDF8] font-mono capitalize">{user?.role}</p>
                </div>
              </div>
              <button 
                onClick={() => setMobileMenuOpen(false)}
                className="p-2 text-gray-400 hover:text-white rounded-lg"
              >
                <X size={20} />
              </button>
            </div>
            
            <div className="p-4 flex-1 overflow-y-auto space-y-1">
              <p className="text-[10px] font-mono font-bold text-gray-500 uppercase tracking-widest mb-3 px-3">Navigation</p>
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path || (
                  item.path !== '/dashboard' && 
                  item.path !== '/driver/dashboard' && 
                  item.path !== '/admin/dashboard' && 
                  location.pathname.startsWith(item.path + '/')
                );
                return (
                  <Link
                    key={item.name}
                    to={item.path}
                    onClick={() => setMobileMenuOpen(false)}
                    className={`flex items-center gap-3 px-3.5 py-2.5 rounded-xl transition-all ${
                      isActive 
                        ? 'bg-[#38BDF8] text-[#05070A] font-semibold' 
                        : 'text-gray-300 hover:bg-[#101820]'
                    }`}
                  >
                    <Icon size={18} className={isActive ? 'text-[#05070A]' : 'text-gray-400'} />
                    <span className="text-sm">{item.name}</span>
                    {item.badge > 0 && (
                      <span className="ml-auto bg-[#38BDF8] text-[#05070A] text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                        {item.badge}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
            
            <div className="p-4 border-t border-[#1E293B]">
              <button 
                onClick={handleLogout}
                className="flex w-full items-center gap-3 px-4 py-2.5 text-red-400 hover:bg-[#101820] rounded-xl transition-all text-sm font-medium"
              >
                <LogOut size={18} />
                Sign Out
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Persistent Floating AI Assistant */}
      <ChatWidget />

    </div>
  );
};

export default DashboardLayout;
