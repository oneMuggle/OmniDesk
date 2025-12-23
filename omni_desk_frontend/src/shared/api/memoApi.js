import apiClient from './apiClient';

const memoApi = {
  getAllMemos: () => {
    return apiClient.get('/api/memos/');
  },
  createMemo: (data) => {
    return apiClient.post('/api/memos/', data);
  },
  patchMemo: (id, data) => {
    return apiClient.patch(`/api/memos/${id}/`, data);
  },
  deleteMemo: (id) => {
    return apiClient.delete(`/api/memos/${id}/`);
  },
};

export default memoApi;