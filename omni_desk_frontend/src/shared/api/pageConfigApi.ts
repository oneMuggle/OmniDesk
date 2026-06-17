import apiClient from './apiClient';

// 对应后端 omni_desk_backend/config/models.py PageVisibility
// TODO: 后续 PR 完善类型 - 与 PageVisibilitySerializer 字段对齐
export interface PageConfig {
    id?: number;
    page?: number | { id: number; path: string; name?: string };
    group?: number | { id: number; name: string };
    visible?: boolean;
    [key: string]: unknown;
}

export interface PageConfigUpdate {
    visible?: boolean;
    [key: string]: unknown;
}

const pageConfigApi = {
    getAllPageConfigs: () => apiClient.get<PageConfig[]>('config/page-visibility/'),
    updatePageConfig: (pagePath: string, data: PageConfigUpdate) =>
        apiClient.patch<PageConfig>(`config/page-visibility/${pagePath}/`, data),
};

export default pageConfigApi;