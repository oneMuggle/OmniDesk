import {
  getNewsTypes, createNewsType, updateNewsType, deleteNewsType,
  getNewsArticles, createNewsArticle, updateNewsArticle, deleteNewsArticle,
  getNewsStats,
} from './newsApi';
import apiClient from '../../../shared/api/apiClient';

jest.mock('../../../shared/api/apiClient', () => ({
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
}));

describe('newsApi', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('News Types', () => {
    it('should get all news types', async () => {
      apiClient.get.mockResolvedValue({ data: { results: [] } });
      await getNewsTypes();
      expect(apiClient.get).toHaveBeenCalledWith('news-types/');
    });

    it('should create a news type', async () => {
      apiClient.post.mockResolvedValue({ data: { id: 1, name: '公告' } });
      await createNewsType({ name: '公告' });
      expect(apiClient.post).toHaveBeenCalledWith('news-types/', { name: '公告' });
    });

    it('should update a news type', async () => {
      apiClient.put.mockResolvedValue({ data: { id: 1, name: '更新' } });
      await updateNewsType(1, { name: '更新' });
      expect(apiClient.put).toHaveBeenCalledWith('news-types/1/', { name: '更新' });
    });

    it('should delete a news type', async () => {
      apiClient.delete.mockResolvedValue({});
      await deleteNewsType(1);
      expect(apiClient.delete).toHaveBeenCalledWith('news-types/1/');
    });
  });

  describe('News Articles', () => {
    it('should get all articles without params', async () => {
      apiClient.get.mockResolvedValue({ data: { results: [] } });
      await getNewsArticles();
      expect(apiClient.get).toHaveBeenCalledWith('news-articles/', { params: undefined });
    });

    it('should get articles filtered by type_id', async () => {
      apiClient.get.mockResolvedValue({ data: { results: [] } });
      await getNewsArticles({ type_id: 2 });
      expect(apiClient.get).toHaveBeenCalledWith('news-articles/', { params: { type_id: 2 } });
    });

    it('should create a news article', async () => {
      apiClient.post.mockResolvedValue({ data: { id: 1, title: '新闻' } });
      await createNewsArticle({ title: '新闻', type_id: 1 });
      expect(apiClient.post).toHaveBeenCalledWith('news-articles/', { title: '新闻', type_id: 1 });
    });

    it('should update a news article', async () => {
      apiClient.put.mockResolvedValue({ data: { id: 1, title: '已更新' } });
      await updateNewsArticle(1, { title: '已更新' });
      expect(apiClient.put).toHaveBeenCalledWith('news-articles/1/', { title: '已更新' });
    });

    it('should delete a news article', async () => {
      apiClient.delete.mockResolvedValue({});
      await deleteNewsArticle(1);
      expect(apiClient.delete).toHaveBeenCalledWith('news-articles/1/');
    });
  });

  describe('News Stats', () => {
    it('should get news stats', async () => {
      apiClient.get.mockResolvedValue({ data: { total: 10 } });
      const result = await getNewsStats();
      expect(apiClient.get).toHaveBeenCalledWith('news-stats/');
      expect(result.data.total).toBe(10);
    });
  });
});
