import apiClient from './apiClient';

const pageConfigApi = {
    getAllPageConfigs: () => apiClient.get('/api/config/page-visibility/'),
    updatePageConfig: (pagePath, data) => apiClient.patch(`/api/config/page-visibility/${pagePath}/`, data),
};

export default pageConfigApi;