import { useState, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './context/AuthContext';
import { WebSocketProvider } from './context/WebSocketContext';
import OpeningAnimation from './components/OpeningAnimation';
import ErrorBoundary from './components/ErrorBoundary';

// Layouts
import AuthLayout from './layouts/AuthLayout';
import DashboardLayout from './layouts/DashboardLayout';

// Auth pages (eager for instant first paint)
import Login from './pages/Login';
import Register from './pages/Register';

// Shared pages (code-split)
const Profile = lazy(() => import('./pages/Profile'));
const Notifications = lazy(() => import('./pages/Notifications'));
const AIAssistantPage = lazy(() => import('./pages/shared/AIAssistantPage'));

// Passenger pages (code-split)
const PassengerDashboard = lazy(() => import('./pages/passenger/PassengerDashboard'));
const BookRide = lazy(() => import('./pages/passenger/BookRide'));
const RideHistory = lazy(() => import('./pages/passenger/RideHistory'));
const RideDetails = lazy(() => import('./pages/passenger/RideDetails'));
const Payments = lazy(() => import('./pages/passenger/Payments'));
const SafetyCenter = lazy(() => import('./pages/passenger/SafetyCenter'));
const SharedRideTracking = lazy(() => import('./pages/shared/SharedRideTracking'));

// Driver pages (code-split)
const DriverDashboard = lazy(() => import('./pages/driver/DriverDashboard'));
const DriverRides = lazy(() => import('./pages/driver/DriverRides'));
const DriverRideDetails = lazy(() => import('./pages/driver/DriverRideDetails'));
const DriverEarnings = lazy(() => import('./pages/driver/DriverEarnings'));
const DriverCopilot = lazy(() => import('./pages/driver/DriverCopilot'));

// Admin pages (code-split)
const AdminDashboard = lazy(() => import('./pages/admin/AdminDashboard'));

// Command-center themed route fallback loader
const PageLoader = () => (
  <div className="flex h-[50vh] w-full items-center justify-center">
    <div className="flex flex-col items-center gap-3">
      <div className="w-8 h-8 rounded-full border-2 border-[#38BDF8] border-t-transparent animate-spin" />
      <span className="text-xs font-mono text-gray-500 uppercase tracking-widest">Loading Telemetry...</span>
    </div>
  </div>
);

// Helper to redirect to correct dashboard based on role
const getHomeRouteForRole = (role) => {
  if (role === 'admin') return '/admin/dashboard';
  if (role === 'driver') return '/driver/dashboard';
  return '/dashboard';

};

// Route Guards
const ProtectedRoute = ({ children, allowedRole }) => {
  const { user, loading } = useAuth();
  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-bg-primary">
      <div className="w-8 h-8 border-4 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
  );
  if (!user) return <Navigate to="/login" replace />;
  if (allowedRole && user.role !== allowedRole) {
    return <Navigate to={getHomeRouteForRole(user.role)} replace />;
  }
  return children;
};

const AuthRoute = ({ children }) => {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to={getHomeRouteForRole(user.role)} replace />;
  return children;
};

function App() {
  const [animationComplete, setAnimationComplete] = useState(false);

  return (
    <>
      {/* Opening cinematic animation — plays once, skippable */}
      {!animationComplete && (
        <OpeningAnimation onComplete={() => setAnimationComplete(true)} />
      )}

      {/* Main application (rendered behind animation, becomes visible after) */}
      <div
        style={{
          opacity: animationComplete ? 1 : 0,
          transition: 'opacity 0.5s ease-out',
        }}
      >
        <ErrorBoundary>
          <BrowserRouter>
      <AuthProvider>
        <Toaster
          position="top-center"
          toastOptions={{
            duration: 3500,
            style: {
              background: '#0a0f14',
              color: '#f1f5f9',
              border: '1px solid #1e293b',
              borderRadius: '12px',
              padding: '12px 20px',
              fontSize: '14px',
              fontWeight: '500',
              boxShadow: '0 10px 30px -5px rgba(0,0,0,0.5)',
            },
            success: { 
              style: { 
                background: '#0a1a14', 
                border: '1px solid #059669',
                color: '#34d399'
              } 
            },
            error: { 
              style: { 
                background: '#1a0a0a', 
                border: '1px solid #dc2626',
                color: '#f87171' 
              } 
            },
          }}
        />

        <WebSocketProvider>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              {/* Auth Routes */}
              <Route element={<AuthRoute><AuthLayout /></AuthRoute>}>
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />
              </Route>

              {/* Passenger Routes */}
              <Route element={<ProtectedRoute allowedRole="passenger"><DashboardLayout /></ProtectedRoute>}>
                <Route path="/dashboard" element={<PassengerDashboard />} />
                <Route path="/book-ride" element={<BookRide />} />
                <Route path="/rides" element={<RideHistory />} />
                <Route path="/rides/:id" element={<RideDetails />} />
                <Route path="/payments" element={<Payments />} />
                <Route path="/safety" element={<SafetyCenter />} />
                <Route path="/assistant" element={<AIAssistantPage />} />
                <Route path="/notifications" element={<Notifications />} />
                <Route path="/profile" element={<Profile />} />
              </Route>

              {/* Driver Routes */}
              <Route element={<ProtectedRoute allowedRole="driver"><DashboardLayout /></ProtectedRoute>}>
                <Route path="/driver/dashboard" element={<DriverDashboard />} />
                <Route path="/driver/rides" element={<DriverRides />} />
                <Route path="/driver/rides/:id" element={<DriverRideDetails />} />
                <Route path="/driver/earnings" element={<DriverEarnings />} />
                <Route path="/driver/copilot" element={<DriverCopilot />} />
                <Route path="/driver/assistant" element={<AIAssistantPage />} />
                <Route path="/driver/notifications" element={<Notifications />} />
                <Route path="/driver/profile" element={<Profile />} />
              </Route>

              {/* Admin Routes */}
              <Route element={<ProtectedRoute allowedRole="admin"><DashboardLayout /></ProtectedRoute>}>
                <Route path="/admin/dashboard" element={<AdminDashboard />} />
                <Route path="/admin/assistant" element={<AIAssistantPage />} />
                <Route path="/admin/notifications" element={<Notifications />} />
                <Route path="/admin/profile" element={<Profile />} />
              </Route>

              {/* Public Live Trip Tracking (No Auth Required) */}
              <Route path="/safety/share/:token" element={<SharedRideTracking />} />

              {/* Redirect root → login */}
              <Route path="/" element={<Navigate to="/login" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </WebSocketProvider>

      </AuthProvider>
    </BrowserRouter>
        </ErrorBoundary>
      </div>
    </>
  );
}

export default App;
