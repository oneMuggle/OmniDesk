import apiClient from './apiClient';

const memoApi = {
  getAllMemos: () => {
    return apiClient.get('/memos/');
  },
  createMemo: (data) => {
    return apiClient.post('/memos/', data);
  },
  patchMemo: (id, data) => {
    return apiClient.patch(`/memos/${id}/`, data);
  },
  deleteMemo: (id) => {
    return apiClient.delete(`/memos/${id}/`);
  },
};

export default memoApi;