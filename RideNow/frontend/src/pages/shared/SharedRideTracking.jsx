import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Shield, ShieldCheck, ShieldAlert, Car, MapPin, Navigation, Clock, AlertCircle, Loader2 } from 'lucide-react';
import Map from '../../components/Map';
import safetyService from '../../services/safetyService';

const SharedRideTracking = () => {
  const { token } = useParams();
  const [rideData, setRideData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchStatus = async () => {
    try {
      const data = await safetyService.getSharedRideStatus(token);
      setRideData(data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'This ride share link has expired or been revoked.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, [token]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#05070A] flex items-center justify-center p-4">
        <Loader2 className="w-8 h-8 animate-spin text-[#38BDF8]" />
      </div>
    );
  }

  if (error || !rideData) {
    return (
      <div className="min-h-screen bg-[#05070A] flex items-center justify-center p-4">
        <div className="card max-w-md w-full p-8 bg-[#0A0F14] border border-[#1E293B] rounded-2xl text-center shadow-2xl">
          <div className="w-14 h-14 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center mx-auto mb-4">
            <AlertCircle size={28} />
          </div>
          <h2 className="text-xl font-bold text-[#F5F7FA] mb-2">Link Inactive</h2>
          <p className="text-xs text-gray-400 leading-relaxed">
            {error || 'This live tracking link is no longer active. It may have expired or been revoked by the passenger.'}
          </p>
        </div>
      </div>
    );
  }

  const markers = [];
  if (rideData.driver_latitude && rideData.driver_longitude) {
    markers.push({
      id: 'shared-driver',
      lat: rideData.driver_latitude,
      lng: rideData.driver_longitude,
      type: 'driver',
      popup: `Driver: ${rideData.driver_name || 'Assigned Driver'}`,
    });
  }

  const isEmergency = rideData.safety_status === 'CRITICAL_ALERT';

  return (
    <div className="min-h-screen bg-[#05070A] text-white p-4 md:p-8">
      <div className="max-w-4xl mx-auto space-y-6 animate-fade-in">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#1E293B] pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#38BDF8]/10 border border-[#38BDF8]/30 text-[#38BDF8] flex items-center justify-center font-bold">
              RN
            </div>
            <div>
              <h1 className="text-base font-bold text-[#F5F7FA]">RideNow Live Trip Share</h1>
              <p className="text-xs text-gray-400">Viewing live journey of {rideData.passenger_name}</p>
            </div>
          </div>

          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-mono uppercase ${
            isEmergency 
              ? 'bg-red-500/10 border-red-500/30 text-red-400' 
              : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
          }`}>
            <span className={`w-2 h-2 rounded-full ${isEmergency ? 'bg-red-400 animate-ping' : 'bg-emerald-400'}`} />
            {isEmergency ? 'SOS ACTIVE' : rideData.status}
          </div>
        </div>

        {/* Emergency Alert Banner */}
        {isEmergency && (
          <div className="p-4 bg-red-950/40 border border-red-500/40 rounded-2xl flex items-center gap-3 text-red-200 text-xs">
            <ShieldAlert size={20} className="text-red-400 shrink-0" />
            <div>
              <p className="font-bold text-red-300">Safety Protocol Initiated</p>
              <p className="text-gray-300 text-[11px] mt-0.5">
                The passenger or fleet controller has triggered emergency assistance. Fleet safety operations are currently actively tracking this trip.
              </p>
            </div>
          </div>
        )}

        {/* Map View */}
        <div className="h-[340px] md:h-[420px] rounded-2xl overflow-hidden card p-1 border border-[#1E293B] shadow-xl relative">
          <Map markers={markers} animateDrivers={true} />
        </div>

        {/* Trip Details Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          
          {/* Route Card */}
          <div className="card p-5 bg-[#0A0F14] border border-[#1E293B] rounded-2xl shadow-lg space-y-4">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">Trip Route</h3>
            
            <div className="space-y-3 text-xs">
              <div className="flex items-start gap-2.5">
                <div className="w-5 h-5 rounded-full bg-[#38BDF8]/10 border border-[#38BDF8]/40 text-[#38BDF8] flex items-center justify-center shrink-0 mt-0.5">
                  <MapPin size={11} />
                </div>
                <div>
                  <p className="text-[10px] text-gray-500 uppercase font-mono">Pickup</p>
                  <p className="font-semibold text-gray-200 mt-0.5">{rideData.pickup_location}</p>
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <div className="w-5 h-5 rounded-full bg-emerald-500/10 border border-emerald-500/40 text-emerald-400 flex items-center justify-center shrink-0 mt-0.5">
                  <Navigation size={11} />
                </div>
                <div>
                  <p className="text-[10px] text-gray-500 uppercase font-mono">Destination</p>
                  <p className="font-semibold text-gray-200 mt-0.5">{rideData.dropoff_location}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Vehicle / Driver Card */}
          <div className="card p-5 bg-[#0A0F14] border border-[#1E293B] rounded-2xl shadow-lg space-y-4">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">Fleet Assignment</h3>

            {rideData.driver_name ? (
              <div className="space-y-3 text-xs">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-[#101820] border border-[#1E293B] flex items-center justify-center text-[#38BDF8]">
                    <Car size={20} />
                  </div>
                  <div>
                    <p className="font-bold text-gray-200">Captain {rideData.driver_name}</p>
                    <p className="text-gray-400 text-[11px]">{rideData.vehicle_model || 'Verified RideNow Vehicle'}</p>
                  </div>
                </div>

                {rideData.vehicle_number && (
                  <div className="p-2.5 bg-[#101820] rounded-xl border border-[#1E293B] flex justify-between items-center text-xs">
                    <span className="text-gray-400 font-mono text-[10px]">Plate Number</span>
                    <span className="font-mono font-bold text-gray-200">{rideData.vehicle_number}</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-6 text-gray-500 text-xs">
                <Car size={24} className="mx-auto mb-2 text-gray-600" />
                Driver assignment in progress...
              </div>
            )}
          </div>
        </div>

        {/* Footer info */}
        <div className="text-center text-gray-600 text-[11px] pt-4">
          RideNow Secure Mobility • Live Telemetry Guard
        </div>

      </div>
    </div>
  );
};

export default SharedRideTracking;
