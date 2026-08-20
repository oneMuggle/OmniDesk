import client from './client';

export const listStipends = (params) => client.get('stipends/', { params });
export const getStipend = (id) => client.get(`stipends/${id}/`);
export const lockStipend = (id, notes) =>
  client.post(`stipends/${id}/lock/`, notes ? { notes } : {});
