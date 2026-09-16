import api from './api';

export const submitRating = async (ratingData) => {
  // POST /ratings with { ride_id, target_type, target_id, rating, feedback }
  const response = await api.post('/ratings', ratingData);
  return response.data;
};

export const getRideRating = async (rideId) => {
  const response = await api.get(`/ratings/ride/${rideId}`);
  return response.data;
};

export const getDriverRatings = async (driverId) => {
  const response = await api.get(`/ratings/driver/${driverId}`);
  return response.data;
};


