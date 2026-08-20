import client from './client';

export const listScores = (params) => client.get('scores/', { params });
export const createScore = (data) => client.post('scores/', data);
export const getScore = (id) => client.get(`scores/${id}/`);
export const updateScore = (id, data) => client.patch(`scores/${id}/`, data);
export const unlockScore = (id) => client.post(`scores/${id}/unlock/`);
