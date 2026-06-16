import * as externalLinksApi from './externalLinksApi';
import axiosInstance from '../../../shared/api/axiosConfig.js';

jest.mock('../../../shared/api/axiosConfig', () => ({
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
}));

describe('externalLinksApi', () => {
  beforeEach(() => jest.clearAllMocks());

  it('fetchExternalLinks 应调用 GET', async () => {
    axiosInstance.get.mockResolvedValue({ data: [{ id: 1 }] });
    const result = await externalLinksApi.fetchExternalLinks();
    expect(axiosInstance.get).toHaveBeenCalledWith('/external/external-links/');
    expect(result).toHaveLength(1);
  });

  it('createExternalLink 应调用 POST', async () => {
    axiosInstance.post.mockResolvedValue({ data: { id: 1 } });
    const result = await externalLinksApi.createExternalLink({ name: 'New' });
    expect(axiosInstance.post).toHaveBeenCalledWith('/external/external-links/', { name: 'New' });
  });

  it('updateExternalLink 应调用 PUT', async () => {
    axiosInstance.put.mockResolvedValue({ data: { id: 1 } });
    await externalLinksApi.updateExternalLink(1, { name: 'Updated' });
    expect(axiosInstance.put).toHaveBeenCalledWith('/external/external-links/1/', { name: 'Updated' });
  });

  it('deleteExternalLink 应调用 DELETE', async () => {
    axiosInstance.delete.mockResolvedValue({});
    await externalLinksApi.deleteExternalLink(1);
    expect(axiosInstance.delete).toHaveBeenCalledWith('/external/external-links/1/');
  });
});
