import apiClient from './apiClient';

const memoApi = {
  // 获取所有备忘录
  getAllMemos: async () => {
    const response = await apiClient.get('memos/');
    return response.data;
  },

  // 获取单个备忘录
  getMemo: (id) => {
    return apiClient.get(`memos/${id}/`);
  },

  // 创建新备忘录
  createMemo: (memoData) => {
    return apiClient.post('memos/', memoData);
  },

  // 更新备忘录
  updateMemo: (id, memoData) => {
    return apiClient.put(`memos/${id}/`, memoData);
  },

  // 部分更新备忘录
  patchMemo: (id, memoData) => {
    return apiClient.patch(`memos/${id}/`, memoData);
  },

  // 删除备忘录
  deleteMemo: (id) => {
    return apiClient.delete(`memos/${id}/`);
  },
};

export default memoApi;