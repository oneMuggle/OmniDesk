import * as pluginApi from './pluginApi';
import axiosInstance from '../../../shared/api/axiosConfig.js';

jest.mock('../../../shared/api/axiosConfig.js', () => ({
  get: jest.fn(),
  post: jest.fn(),
}));

describe('pluginApi', () => {
  beforeEach(() => jest.clearAllMocks());

  it('fetchPlugins 应调用 GET', async () => {
    axiosInstance.get.mockResolvedValue({ data: [{ id: 1 }] });
    const result = await pluginApi.fetchPlugins();
    expect(axiosInstance.get).toHaveBeenCalledWith('/external/plugins/', { params: {} });
    expect(result).toHaveLength(1);
  });

  it('fetchPluginDetail 应调用 GET/:id', async () => {
    axiosInstance.get.mockResolvedValue({ data: { id: 1 } });
    const result = await pluginApi.fetchPluginDetail(1);
    expect(axiosInstance.get).toHaveBeenCalledWith('/external/plugins/1/');
    expect(result.id).toBe(1);
  });

  it('uploadPluginVersion 应调用 POST', async () => {
    axiosInstance.post.mockResolvedValue({ data: { success: true } });
    const formData = new FormData();
    await pluginApi.uploadPluginVersion(1, formData);
    expect(axiosInstance.post).toHaveBeenCalledWith('/external/plugins/1/upload_version/', formData, expect.any(Object));
  });

  it('executePlugin 应调用 POST', async () => {
    axiosInstance.post.mockResolvedValue({ data: { result: 'ok' } });
    const result = await pluginApi.executePlugin(1, { param: 'value' });
    expect(axiosInstance.post).toHaveBeenCalledWith('/external/plugins/1/execute/', { params: { param: 'value' } });
  });
});
