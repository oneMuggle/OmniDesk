import client from './client';

export const listStudents = (params) => client.get('students/', { params });
export const getStudent = (id) => client.get(`students/${id}/`);
export const createStudent = (data) => client.post('students/', data);
export const updateStudent = (id, data) => client.patch(`students/${id}/`, data);
export const deleteStudent = (id) => client.delete(`students/${id}/`);
export const graduateStudent = (id) => client.post(`students/${id}/graduate/`);
export const listPersonnelPool = () => client.get('personnel-pool/');
