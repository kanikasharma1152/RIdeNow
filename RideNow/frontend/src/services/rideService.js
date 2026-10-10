import api from './api';

export const requestRide = async (rideData) => {
  const response = await api.post('/rides/request', rideData);
  return response.data;
};

export const getPassengerRides = async (params = {}) => {
  const response = await api.get('/rides/my', { params });
  return response.data;
};

export const getMyRides = getPassengerRides;

export const getPassengerRideHistory = async (params = {}) => {
  const response = await api.get('/rides/my/history', { params });
  return response.data;
};


export const getAvailableRides = async () => {
  const response = await api.get('/rides/available');
  return response.data;
};

export const matchDriver = async (rideId) => {
  const response = await api.patch(`/rides/${rideId}/match`);
  return response.data;
};

export const acceptRide = async (rideId) => {
  const response = await api.patch(`/rides/${rideId}/accept`);
  return response.data;
};

export const rejectRide = async (rideId) => {
  const response = await api.post(`/rides/${rideId}/reject`);
  return response.data;
};

export const getDriverRides = async (params = {}) => {
  const response = await api.get('/rides/driver/my', { params });
  return response.data;
};

export const getDriverRideHistory = async (params = {}) => {
  const response = await api.get('/rides/driver/my/history', { params });
  return response.data;
};

export const startRide = async (rideId) => {
  const response = await api.patch(`/rides/${rideId}/start`);
  return response.data;
};

export const completeRide = async (rideId) => {
  const response = await api.patch(`/rides/${rideId}/complete`);
  return response.data;
};

export const cancelRide = async (rideId) => {
  const response = await api.patch(`/rides/${rideId}/cancel`);
  return response.data;
};

export const getRide = async (rideId) => {
  const response = await api.get(`/rides/${rideId}`);
  return response.data;
};

/**
 * Get fare estimate before booking — no ride is created.
 * Returns { distance_km, estimated_fare, base_fare, per_km_rate, currency,
 *           pickup_latitude, pickup_longitude, dropoff_latitude, dropoff_longitude }
 */
export const getFareEstimate = async (pickup_location, dropoff_location) => {
  const response = await api.get('/rides/fare-estimate', {
    params: { pickup_location, dropoff_location },
  });
  return response.data;
};
