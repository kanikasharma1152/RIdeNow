import api from './api';

export const mobilityService = {
  // Plan an end-to-end trip backwards from arrival deadline or departure
  getTripPlan: async (planRequest) => {
    const res = await api.post('/mobility/trip-plan', planRequest);
    return res.data;
  },

  // Retrieve user's personal mobility analytics and lifetime spend
  getMyMobilitySummary: async () => {
    const res = await api.get('/mobility/summary');
    return res.data;
  },

  // Suggest curbside and landmark pickup points
  getSmartPickupPoints: async (lat, lon, address = '') => {
    const res = await api.get('/mobility/smart-pickup', {
      params: { lat, lon, address },
    });
    return res.data;
  },

  // Get real-time departure and timing recommendations
  getTravelRecommendation: async (destination, origin = 'Current Location', targetTime = null) => {
    const res = await api.get('/mobility/recommendation', {
      params: { destination, origin, target_time: targetTime },
    });
    return res.data;
  },

  // Explain how driver matching evaluates proximity, congestion, ratings & acceptance
  getMatchingExplanation: async (lat = 22.7196, lon = 75.8577) => {
    const res = await api.get('/mobility/matching-explanation', {
      params: { lat, lon },
    });
    return res.data;
  },
};

export default mobilityService;
