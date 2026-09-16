import api, { getErrorMessage } from './api';

export const sendChatMessage = async (message) => {
  try {
    const response = await api.post('/chat/message', { message });
    return response.data;
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
};

export const clearChatHistory = async () => {
  try {
    const response = await api.delete('/chat/history');
    return response.data;
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
};
