import { Outlet } from 'react-router-dom';
import { Car } from 'lucide-react';

const AuthLayout = () => {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col md:flex-row">
      {/* Left side: Branding / Visuals (Hidden on Mobile) */}
      <div className="hidden md:flex md:w-1/2 bg-brand-950 text-white flex-col justify-between p-12 lg:p-20 relative overflow-hidden">
        {/* Subtle background decoration */}
        <div className="absolute top-0 right-0 -mr-20 -mt-20 w-96 h-96 rounded-full bg-white opacity-5 blur-3xl"></div>
        <div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-80 h-80 rounded-full bg-accent opacity-20 blur-3xl"></div>
        
        <div className="relative z-10">
          <div className="flex items-center gap-3 text-3xl font-bold tracking-tight mb-6">
            <div className="w-10 h-10 bg-white text-brand-950 flex items-center justify-center rounded-xl shadow-lg">
              <Car size={24} />
            </div>
            RideNow
          </div>
          <h1 className="text-4xl lg:text-5xl font-semibold leading-tight mb-6">
            Your city,<br />
            your schedule.
          </h1>
          <p className="text-lg text-gray-400 max-w-md">
            The premium ride-booking experience. Fast, reliable, and comfortable mobility at your fingertips.
          </p>
        </div>

        <div className="relative z-10">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-full border-2 border-gray-700 overflow-hidden bg-gray-800">
              <img src="https://ui-avatars.com/api/?name=User&background=333&color=fff" alt="User avatar" />
            </div>
            <div>
              <p className="font-medium">"Best ride experience in the city."</p>
              <p className="text-sm text-gray-500">Rated 4.9/5 by 10,000+ users</p>
            </div>
          </div>
        </div>
      </div>

      {/* Right side: Auth Form */}
      <div className="w-full md:w-1/2 flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-md">
          {/* Mobile branding only shown on small screens */}
          <div className="md:hidden flex items-center justify-center gap-3 text-3xl font-bold tracking-tight mb-10 text-brand-950">
            <div className="w-10 h-10 bg-brand-950 text-white flex items-center justify-center rounded-xl shadow-md">
              <Car size={24} />
            </div>
            RideNow
          </div>
          
          <Outlet />
        </div>
      </div>
    </div>
  );
};

export default AuthLayout;
