import apiClient from './apiClient';

const pageConfigApi = {
    getAllPageConfigs: () => apiClient.get('/config/pages/'),
    updatePageConfig: (pagePath, data) => apiClient.patch(`/config/pages/${pagePath}/`, data),
};

export default pageConfigApi;