import api from './api';

export const getAdminOverview = async () => {
  const response = await api.get('/admin/analytics/overview');
  return response.data;
};

export const getAdminAIInsights = async () => {
  const response = await api.get('/admin/analytics/insights');
  return response.data;
};

export default {
  getAdminOverview,
  getAdminAIInsights,
};
