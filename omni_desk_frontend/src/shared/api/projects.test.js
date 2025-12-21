import projectsApi from '../../features/projects/api/projects';
import apiClient from './apiClient';

jest.mock('./apiClient');

describe('projectsApi', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should fetch all projects', async () => {
    const response = { data: [{ id: 1, name: 'Project 1' }] };
    apiClient.get.mockResolvedValue(response);

    await projectsApi.getAllProjects();

    expect(apiClient.get).toHaveBeenCalledWith('/projects/');
  });

  it('should fetch a project by id', async () => {
    const id = 1;
    const response = { data: { id: 1, name: 'Project 1' } };
    apiClient.get.mockResolvedValue(response);

    await projectsApi.getProjectById(id);

    expect(apiClient.get).toHaveBeenCalledWith(`/projects/${id}/`);
  });

  it('should create a new project', async () => {
    const projectData = { name: 'New Project' };
    const response = { data: { id: 2, ...projectData } };
    apiClient.post.mockResolvedValue(response);

    await projectsApi.createProject(projectData);

    expect(apiClient.post).toHaveBeenCalledWith('/projects/', projectData);
  });

  it('should update a project', async () => {
    const id = 1;
    const projectData = { name: 'Updated Project' };
    const response = { data: { id: 1, ...projectData } };
    apiClient.put.mockResolvedValue(response);

    await projectsApi.updateProject(id, projectData);

    expect(apiClient.put).toHaveBeenCalledWith(`/projects/${id}/`, projectData);
  });

  it('should partially update a project', async () => {
    const id = 1;
    const projectData = { name: 'Partially Updated Project' };
    const response = { data: { id: 1, ...projectData } };
    apiClient.patch.mockResolvedValue(response);

    await projectsApi.partialUpdateProject(id, projectData);

    expect(apiClient.patch).toHaveBeenCalledWith(`/projects/${id}/`, projectData);
  });

  it('should delete a project', async () => {
    const id = 1;
    apiClient.delete.mockResolvedValue({});

    await projectsApi.deleteProject(id);

    expect(apiClient.delete).toHaveBeenCalledWith(`/projects/${id}/`);
  });
});