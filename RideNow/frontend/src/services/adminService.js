import api from './api';

export const getAdminOverview = async () => {
  const response = await api.get('/admin/analytics/overview');
  return response.data;
};

export const getAdminAIInsights = async () => {
  const response = await api.get('/admin/analytics/insights');
  return response.data;
};

/**
 * Fetch ML-computed demand hotspots for live fleet map overlay.
 * Returns array of { zone_id, latitude, longitude, demand_score, label }.
 */
export const getMLDemandHotspots = async (limit = 8) => {
  const response = await api.get('/ml/demand/hotspots', { params: { limit } });
  return response.data;
};

// ─── Phase 14: System Health & Reliability ───────────────────────────────────

export const getSystemHealth = async () => {
  const response = await api.get('/health/system');
  return response.data;
};

export const getAIMetrics = async () => {
  const response = await api.get('/health/ai');
  return response.data;
};

export const getAdminIntelligence = async () => {
  const response = await api.get('/admin/intelligence');
  return response.data;
};

export const getRideReliability = async () => {
  const response = await api.get('/admin/ride-reliability');
  return response.data;
};

export default {
  getAdminOverview,
  getAdminAIInsights,
  getMLDemandHotspots,
  getSystemHealth,
  getAIMetrics,
  getAdminIntelligence,
  getRideReliability,
};
