import api from './api';

export const analyzeLocationImage = async (file, query = '', coords = null) => {
  const formData = new FormData();
  formData.append('image', file);
  if (query) formData.append('query', query);
  if (coords?.latitude) formData.append('latitude', coords.latitude);
  if (coords?.longitude) formData.append('longitude', coords.longitude);

  const response = await api.post('/vision/analyze-location', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};
