import apiClient from '../../../shared/api/apiClient';

const projectsApi = {
    getAllProjects: () => apiClient.get('/api/projects/'),
    getProjectById: (id) => apiClient.get(`/api/projects/${id}/`),
    createProject: (projectData) => apiClient.post('/api/projects/', projectData),
    updateProject: (id, projectData) => apiClient.put(`/api/projects/${id}/`, projectData),
    partialUpdateProject: (id, projectData) => apiClient.patch(`/api/projects/${id}/`, projectData),
    deleteProject: (id) => apiClient.delete(`/api/projects/${id}/`),
};

export default projectsApi;