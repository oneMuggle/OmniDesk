import apiClient from './apiClient';

const projectsApi = {
    getAllProjects: () => apiClient.get('/projects/'),
    getProjectById: (id) => apiClient.get(`/projects/${id}/`),
    createProject: (projectData) => apiClient.post('/projects/', projectData),
    updateProject: (id, projectData) => apiClient.put(`/projects/${id}/`, projectData),
    partialUpdateProject: (id, projectData) => apiClient.patch(`/projects/${id}/`, projectData),
    deleteProject: (id) => apiClient.delete(`/projects/${id}/`),
};

export default projectsApi;