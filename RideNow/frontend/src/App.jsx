import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './context/AuthContext';
import { WebSocketProvider } from './context/WebSocketContext';

// Layouts
import AuthLayout from './layouts/AuthLayout';
import DashboardLayout from './layouts/DashboardLayout';

// Auth pages
import Login from './pages/Login';
import Register from './pages/Register';

// Shared pages
import Profile from './pages/Profile';
import Notifications from './pages/Notifications';
import AIAssistantPage from './pages/shared/AIAssistantPage';

// Passenger pages
import PassengerDashboard from './pages/passenger/PassengerDashboard';
import BookRide from './pages/passenger/BookRide';
import RideHistory from './pages/passenger/RideHistory';
import RideDetails from './pages/passenger/RideDetails';
import Payments from './pages/passenger/Payments';

// Driver pages
import DriverDashboard from './pages/driver/DriverDashboard';
import DriverRides from './pages/driver/DriverRides';
import DriverRideDetails from './pages/driver/DriverRideDetails';
import DriverEarnings from './pages/driver/DriverEarnings';
import DriverCopilot from './pages/driver/DriverCopilot';

// Admin pages
import AdminDashboard from './pages/admin/AdminDashboard';

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
  return (
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

            {/* Redirect root → login */}
            <Route path="/" element={<Navigate to="/login" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </WebSocketProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;

