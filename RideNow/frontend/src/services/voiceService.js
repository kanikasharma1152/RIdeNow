import api from './api';

export const getVoiceToken = async (roomName = null) => {
  const payload = roomName ? { room_name: roomName } : {};
  const response = await api.post('/voice/token', payload);
  return response.data;
};

export default {
  getVoiceToken,
};
