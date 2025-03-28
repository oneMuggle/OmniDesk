import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL;

const getAuthHeaders = () => ({
  headers: {
    Authorization: `Bearer ${localStorage.getItem('accessToken')}`,
  }
});

export const fetchEquipment = async (params) => {
    try {
        const response = await axios.get(`${API_URL}/equipment/`, { params, ...getAuthHeaders() });
        return response.data;
    } catch (error) {
        console.error('获取设备列表失败:', error);
        throw error;
    }
};

export const createEquipment = async (equipmentData) => {
    try {
        const response = await axios.post(`${API_URL}/equipment/`, equipmentData, getAuthHeaders());
        return response.data;
    } catch (error) {
        console.error('创建设备失败:', error);
        throw error;
    }
};

export const updateEquipment = async (id, equipmentData) => {
    try {
        const response = await axios.put(`${API_URL}/equipment/${id}/`, equipmentData, getAuthHeaders());
        return response.data;
    } catch (error) {
        console.error('更新设备失败:', error);
        throw error;
    }
};

export const deleteEquipment = async (id) => {
    try {
        await axios.delete(`${API_URL}/equipment/${id}/`, getAuthHeaders());
    } catch (error) {
        console.error('删除设备失败:', error);
        throw error;
    }
};
