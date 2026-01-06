import axios from 'axios';

export const saveResponsiblePersons = async (persons) => {
  try {
    const response = await axios.post('events/responsible_persons/', {
      responsibles: persons
    });
    return response.data;
  } catch (error) {
    throw new Error('保存负责人信息失败: ' + (error.response?.data?.message || error.message));
  }
};
