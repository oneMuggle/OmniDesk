import apiClient from '../../../shared/api/apiClient';

// Centralized error handler
const handleError = (error, defaultMessage = '操作失败') => {
  if (!error.response) {
    throw { message: '网络连接异常，请检查网络后重试' };
  }
  if (error.response.status === 401) {
    // Trigger re-authentication flow
    window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname);
    // Return a promise that never resolves to stop further execution
    return new Promise(() => {});
  }
  throw error.response.data || { message: defaultMessage };
};

// Centralized handler for paginated responses
const handlePaginatedResponse = (response) => {
  return {
    data: response.data.results || [],
    pagination: {
      current: response.data.current_page || 1,
      total: response.data.count || 0,
      pageSize: response.data.page_size || 10,
    },
  };
};

// Personnel API
export const getPersonnel = async (params = {}) => {
  try {
    const response = await apiClient.get('personnel/personnel/', { params });
    return handlePaginatedResponse(response);
  } catch (error) {
    return handleError(error, '获取人员列表失败');
  }
};

export const getAllPersonnel = () => {
  return apiClient.get('personnel/personnel/', { params: { page_size: 1000 } });
};

export const getPersonnelDetails = async (id) => {
  try {
    const response = await apiClient.get(`personnel/personnel/${id}/`);
    return response.data;
  } catch (error) {
    return handleError(error, '获取人员详细信息失败');
  }
};

export const createPersonnel = async (data) => {
  try {
    const response = await apiClient.post('personnel/personnel/', data);
    return response.data;
  } catch (error) {
    return handleError(error, '创建人员信息失败');
  }
};

export const updatePersonnel = async (id, data) => {
  try {
    const response = await apiClient.put(`personnel/personnel/${id}/`, data);
    return response.data;
  } catch (error) {
    return handleError(error, '更新人员信息失败');
  }
};

export const deletePersonnel = async (id) => {
  try {
    await apiClient.delete(`personnel/personnel/${id}/`);
    return { success: true };
  } catch (error) {
    return handleError(error, '删除人员信息失败');
  }
};

// Position API
export const getPositions = (params = {}) => {
  return apiClient.get('personnel/positions/', { params });
};

export const getAllPositions = async () => {
  try {
    const response = await apiClient.get('personnel/positions/', { params: { page_size: 1000 } });
    return response.data.results || [];
  } catch (error) {
    return handleError(error, '获取所有职位信息失败');
  }
};

export const createPosition = async (data) => {
  try {
    const response = await apiClient.post('personnel/positions/', data);
    return response.data;
  } catch (error) {
    return handleError(error, '创建职位失败');
  }
};

export const updatePosition = async (id, data) => {
  try {
    const response = await apiClient.put(`personnel/positions/${id}/`, data);
    return response.data;
  } catch (error) {
    return handleError(error, '更新职位失败');
  }
};

export const deletePosition = async (id) => {
  try {
    await apiClient.delete(`personnel/positions/${id}/`);
    return { success: true };
  } catch (error) {
    return handleError(error, '删除职位失败');
  }
};

// Professional Qualifications API
export const getQualifications = async (personnelId) => {
  try {
    const response = await apiClient.get(`personnel/qualifications/?personnel=${personnelId}`);
    return response.data || [];
  } catch (error) {
    return handleError(error, '获取专业资格失败');
  }
};

export const createQualification = async (data) => {
  try {
    const response = await apiClient.post('personnel/qualifications/', data);
    return response.data;
  } catch (error) {
    return handleError(error, '创建专业资格失败');
  }
};

export const updateQualification = async (id, data) => {
  try {
    const response = await apiClient.put(`personnel/qualifications/${id}/`, data);
    return response.data;
  } catch (error) {
    return handleError(error, '更新专业资格失败');
  }
};

export const deleteQualification = async (id) => {
  try {
    await apiClient.delete(`personnel/qualifications/${id}/`);
    return { success: true };
  } catch (error) {
    return handleError(error, '删除专业资格失败');
  }
};

// Family Members API
export const getFamilyMembers = async (personnelId) => {
  try {
    const response = await apiClient.get(`personnel/family-members/?personnel=${personnelId}`);
    return response.data || [];
  } catch (error) {
    return handleError(error, '获取家庭成员失败');
  }
};

export const createFamilyMember = async (data) => {
  try {
    const response = await apiClient.post('personnel/family-members/', data);
    return response.data;
  } catch (error) {
    return handleError(error, '创建家庭成员失败');
  }
};

export const updateFamilyMember = async (id, data) => {
  try {
    const response = await apiClient.put(`personnel/family-members/${id}/`, data);
    return response.data;
  } catch (error) {
    return handleError(error, '更新家庭成员失败');
  }
};

export const deleteFamilyMember = async (id) => {
  try {
    await apiClient.delete(`personnel/family-members/${id}/`);
    return { success: true };
  } catch (error) {
    return handleError(error, '删除家庭成员失败');
  }
};

// My Personnel (P2-3) — 当前登录用户自助维护入口
export const getMyPersonnel = async () => {
  try {
    const response = await apiClient.get('users/me/personnel/');
    return response.data;
  } catch (error) {
    return handleError(error, '获取我的信息失败');
  }
};

export const updateMyPersonnel = async (data) => {
  try {
    const response = await apiClient.patch('users/me/personnel/', data);
    return response.data;
  } catch (error) {
    return handleError(error, '更新我的信息失败');
  }
};
