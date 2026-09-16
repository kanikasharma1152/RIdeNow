import api from './api';

export const getDriverBriefing = async () => {
  const response = await api.get('/driver/copilot/briefing');
  return response.data;
};

export const chatDriverCopilot = async (message) => {
  const response = await api.post('/driver/copilot/chat', { message });
  return response.data;
};

export default {
  getDriverBriefing,
  chatDriverCopilot,
};
