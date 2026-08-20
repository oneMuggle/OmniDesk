import client from './client';

export const listCycles = (params) => client.get('cycles/', { params });
export const getCycle = (id) => client.get(`cycles/${id}/`);
export const triggerCycle = (data) => client.post('cycles/trigger/', data);
export const forceCloseCycle = (id) => client.post(`cycles/${id}/force_close/`);
export const listCycleScores = (id, params) => client.get(`cycles/${id}/scores/`, { params });
export const listCycleStipends = (id, params) => client.get(`cycles/${id}/stipends/`, { params });
