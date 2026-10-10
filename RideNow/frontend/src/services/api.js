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
    // Extract request-id from response header if available
    const requestId = error.response?.headers?.['x-request-id'] || error.response?.data?.error?.request_id;
    if (requestId) {
      error.requestId = requestId;
    }

    // Handle 401 Unauthorized globally
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('token');
      if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export const getErrorMessage = (error, defaultMsg = 'Something went wrong') => {
  if (!error?.response) {
    return 'Connection lost. Please check your network and try again.';
  }

  const status = error.response.status;
  const requestId = error.requestId || error.response?.headers?.['x-request-id'];
  const reqSuffix = requestId ? ` (Ref: ${requestId})` : '';

  if (status === 429) {
    return 'Too many requests. Please wait a moment and try again.';
  }
  if (status === 503) {
    return `RideNow service is temporarily unavailable. Please try again in a few moments.${reqSuffix}`;
  }
  if (status >= 500) {
    return `A server error occurred. Please try again.${reqSuffix}`;
  }

  if (error?.response?.data?.error?.message) {
    return `${error.response.data.error.message}${reqSuffix}`;
  }
  if (typeof error?.response?.data?.detail === 'string') {
    return `${error.response.data.detail}${reqSuffix}`;
  }
  if (Array.isArray(error?.response?.data?.detail) && error.response.data.detail.length > 0) {
    const firstErr = error.response.data.detail[0];
    const field = firstErr.loc?.slice(-1)[0];
    return `${field ? field + ': ' : ''}${firstErr.msg}${reqSuffix}`;
  }
  return `${error?.message || defaultMsg}${reqSuffix}`;
};

export default api;
