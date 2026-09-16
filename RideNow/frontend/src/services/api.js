import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle 401 Unauthorized globally
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('token');
      // Using window.location to avoid circular dependencies with React Router
      if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export const getErrorMessage = (error, defaultMsg = 'Something went wrong') => {
  if (error?.response?.data?.error?.message) {
    return error.response.data.error.message;
  }
  if (typeof error?.response?.data?.detail === 'string') {
    return error.response.data.detail;
  }
  if (Array.isArray(error?.response?.data?.detail) && error.response.data.detail.length > 0) {
    const firstErr = error.response.data.detail[0];
    const field = firstErr.loc?.slice(-1)[0];
    return `${field ? field + ': ' : ''}${firstErr.msg}`;
  }
  return error?.message || defaultMsg;
};

export default api;
