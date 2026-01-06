import apiClient from './apiClient';

const pageConfigApi = {
    getAllPageConfigs: () => apiClient.get('config/page-visibility/'),
    updatePageConfig: (pagePath, data) => apiClient.patch(`config/page-visibility/${pagePath}/`, data),
};

export default pageConfigApi;