import pageConfigApi from './pageConfigApi';
import apiClient from './apiClient';

jest.mock('./apiClient', () => ({
  get: jest.fn(),
  patch: jest.fn(),
}));

describe('pageConfigApi', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should get all page configs', async () => {
    apiClient.get.mockResolvedValue({ data: { results: [] } });
    await pageConfigApi.getAllPageConfigs();
    expect(apiClient.get).toHaveBeenCalledWith('config/page-visibility/');
  });

  it('should update a page config', async () => {
    apiClient.patch.mockResolvedValue({ data: { visible: true } });
    await pageConfigApi.updatePageConfig('/dashboard', { visible: true });
    expect(apiClient.patch).toHaveBeenCalledWith('config/page-visibility//dashboard/', { visible: true });
  });
});
