import projectsApi from './projects';
import apiClient from '../../../shared/api/apiClient';

jest.mock('../../../shared/api/apiClient', () => ({
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  patch: jest.fn(),
  delete: jest.fn(),
}));

describe('projectsApi', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should get all projects', async () => {
    apiClient.get.mockResolvedValue({ data: { results: [{ id: 1, name: 'Project A' }] } });
    const result = await projectsApi.getAllProjects();
    expect(apiClient.get).toHaveBeenCalledWith('projects/');
    expect(result.data.results).toHaveLength(1);
  });

  it('should get a single project', async () => {
    apiClient.get.mockResolvedValue({ data: { id: 1, name: 'Project A' } });
    await projectsApi.getProjectById(1);
    expect(apiClient.get).toHaveBeenCalledWith('projects/1/');
  });

  it('should create a project', async () => {
    apiClient.post.mockResolvedValue({ data: { id: 1, name: 'New' } });
    await projectsApi.createProject({ name: 'New' });
    expect(apiClient.post).toHaveBeenCalledWith('projects/', { name: 'New' });
  });

  it('should update a project', async () => {
    apiClient.put.mockResolvedValue({ data: { id: 1, name: 'Updated' } });
    await projectsApi.updateProject(1, { name: 'Updated' });
    expect(apiClient.put).toHaveBeenCalledWith('projects/1/', { name: 'Updated' });
  });

  it('should partial update a project', async () => {
    apiClient.patch.mockResolvedValue({ data: { id: 1, name: 'Patched' } });
    await projectsApi.partialUpdateProject(1, { name: 'Patched' });
    expect(apiClient.patch).toHaveBeenCalledWith('projects/1/', { name: 'Patched' });
  });

  it('should delete a project', async () => {
    apiClient.delete.mockResolvedValue({});
    await projectsApi.deleteProject(1);
    expect(apiClient.delete).toHaveBeenCalledWith('projects/1/');
  });
});
