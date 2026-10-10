import api from './api';

export const safetyService = {
  // ─── Safety Center (Phase 13) ──────────────────────────────────────────────
  
  // Full safety center overview
  getSafetyCenter: async () => {
    const res = await api.get('/safety/center');
    return res.data;
  },

  // Active safety events for the current user
  getActiveEvents: async () => {
    const res = await api.get('/safety/active');
    return res.data;
  },

  // Report a safety concern
  reportSafetyConcern: async (data) => {
    const res = await api.post('/safety/events', data);
    return res.data;
  },

  // Acknowledge a safety event
  acknowledgeEvent: async (eventId) => {
    const res = await api.post(`/safety/events/${eventId}/acknowledge`);
    return res.data;
  },

  // Universal SOS (no ride required)
  triggerUniversalSOS: async (data = {}) => {
    const res = await api.post('/safety/sos', data);
    return res.data;
  },

  // Driver SOS
  triggerDriverSOS: async (data = {}) => {
    const res = await api.post('/safety/driver/sos', data);
    return res.data;
  },

  // Check prolonged stop
  checkProlongedStop: async (rideId) => {
    const res = await api.post(`/safety/rides/${rideId}/prolonged-stop`);
    return res.data;
  },

  // ─── Legacy / Existing ────────────────────────────────────────────────────
  
  // SOS Trigger (ride-specific, backward compat)
  triggerSOS: async (rideId, data = {}) => {
    const res = await api.post(`/safety/rides/${rideId}/sos`, data);
    return res.data;
  },

  // Submit telemetry
  submitTelemetry: async (rideId, data) => {
    const res = await api.post(`/safety/rides/${rideId}/telemetry`, data);
    return res.data;
  },

  // Get safety events for a ride
  getRideSafetyEvents: async (rideId) => {
    const res = await api.get(`/safety/rides/${rideId}/events`);
    return res.data;
  },

  // Resolve an event
  resolveSafetyEvent: async (eventId) => {
    const res = await api.patch(`/safety/events/${eventId}/resolve`);
    return res.data;
  },

  // User safety history
  getSafetyHistory: async () => {
    const res = await api.get('/safety/history');
    return res.data;
  },

  // Trusted contacts
  getTrustedContacts: async () => {
    const res = await api.get('/safety/trusted-contacts');
    return res.data;
  },

  addTrustedContact: async (contactData) => {
    const res = await api.post('/safety/trusted-contacts', contactData);
    return res.data;
  },

  updateTrustedContact: async (contactId, contactData) => {
    const res = await api.patch(`/safety/trusted-contacts/${contactId}`, contactData);
    return res.data;
  },

  deleteTrustedContact: async (contactId) => {
    const res = await api.delete(`/safety/trusted-contacts/${contactId}`);
    return res.data;
  },

  // Live ride sharing
  createShareLink: async (rideId) => {
    const res = await api.post(`/safety/rides/${rideId}/share`);
    return res.data;
  },

  revokeShareLink: async (rideId, token) => {
    const res = await api.delete(`/safety/rides/${rideId}/share/${token}`);
    return res.data;
  },

  getSharedRideStatus: async (token) => {
    const res = await api.get(`/safety/share/${token}`);
    return res.data;
  },

  // Admin
  getAdminSafetyMetrics: async () => {
    const res = await api.get('/safety/admin/metrics');
    return res.data;
  },

  getAdminSafetyEvents: async (params = {}) => {
    const res = await api.get('/safety/admin/events', { params });
    return res.data;
  },
};

export default safetyService;
