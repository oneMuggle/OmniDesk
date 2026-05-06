import complianceApi from './compliance';
import apiClient from '../../../shared/api/apiClient';

jest.mock('../../../shared/api/apiClient', () => ({
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  patch: jest.fn(),
  delete: jest.fn(),
}));

describe('complianceApi', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should get all compliance issues', async () => {
    apiClient.get.mockResolvedValue({ data: { results: [] } });
    await complianceApi.getAllComplianceIssues();
    expect(apiClient.get).toHaveBeenCalledWith('compliance/', { params: undefined });
  });

  it('should get compliance issue by id', async () => {
    apiClient.get.mockResolvedValue({ data: { id: 1 } });
    await complianceApi.getComplianceIssueById(1);
    expect(apiClient.get).toHaveBeenCalledWith('compliance/1/');
  });

  it('should create a compliance issue', async () => {
    apiClient.post.mockResolvedValue({ data: { id: 1 } });
    await complianceApi.createComplianceIssue({ title: 'Test' });
    expect(apiClient.post).toHaveBeenCalledWith('compliance/', { title: 'Test' });
  });

  it('should update a compliance issue', async () => {
    apiClient.put.mockResolvedValue({ data: { id: 1 } });
    await complianceApi.updateComplianceIssue(1, { title: 'Updated' });
    expect(apiClient.put).toHaveBeenCalledWith('compliance/1/', { title: 'Updated' });
  });

  it('should partial update a compliance issue', async () => {
    apiClient.patch.mockResolvedValue({ data: { id: 1 } });
    await complianceApi.partialUpdateComplianceIssue(1, { status: 'resolved' });
    expect(apiClient.patch).toHaveBeenCalledWith('compliance/1/', { status: 'resolved' });
  });

  it('should delete a compliance issue', async () => {
    apiClient.delete.mockResolvedValue({});
    await complianceApi.deleteComplianceIssue(1);
    expect(apiClient.delete).toHaveBeenCalledWith('compliance/1/');
  });

  it('should get unread count', async () => {
    apiClient.get.mockResolvedValue({ data: { unread_count: 3 } });
    const result = await complianceApi.getUnreadCount();
    expect(apiClient.get).toHaveBeenCalledWith('compliance/unread_count/');
    expect(result.data.unread_count).toBe(3);
  });
});
