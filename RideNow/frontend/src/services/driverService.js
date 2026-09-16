import api from './api';

export const registerDriver = async (driverData) => {
  const response = await api.post('/drivers/register', driverData);
  return response.data;
};

export const getMyDriverProfile = async () => {
  const response = await api.get('/drivers/me/profile');
  return response.data;
};

export const updateDriverStatus = async (is_online, is_available) => {
  const response = await api.patch('/drivers/status', null, {
    params: { is_online, is_available }
  });
  return response.data;
};

export const updateDriverLocation = async (latitude, longitude) => {
  const response = await api.patch('/drivers/location', { latitude, longitude });
  return response.data;
};

export const updateDriverProfile = async (profileData) => {
  const response = await api.patch('/drivers/me', profileData);
  return response.data;
};

export const getDriverEarnings = async () => {
  const response = await api.get('/drivers/earnings');
  return response.data;
};
