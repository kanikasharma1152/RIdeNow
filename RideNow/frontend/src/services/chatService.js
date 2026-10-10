import api, { getErrorMessage } from './api';

export const sendChatMessage = async (message, options = {}) => {
  try {
    const payload = {
      message,
      input_type: options.inputType || (options.imageBase64 ? 'image' : options.latitude ? 'location' : 'text'),
      image_base64: options.imageBase64 || null,
      latitude: options.latitude ?? null,
      longitude: options.longitude ?? null,
    };
    const response = await api.post('/chat/message', payload);
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
