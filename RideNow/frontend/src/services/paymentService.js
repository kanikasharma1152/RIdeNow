import api from './api';

export const processPayment = async (paymentData) => {
  // POST /payments with { ride_id, amount, payment_method }
  const response = await api.post('/payments', paymentData);
  return response.data;
};

export const completePayment = async (rideId) => {
  const response = await api.patch(`/payments/${rideId}/pay`);
  return response.data;
};

export const getPaymentForRide = async (rideId) => {
  const response = await api.get(`/payments/ride/${rideId}`);
  return response.data;
};
