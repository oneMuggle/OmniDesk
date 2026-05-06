import { getPosts, getPost, createPost, updatePost, deletePost, createComment } from './communicationApi';
import apiClient from '../../../shared/api/apiClient';

jest.mock('../../../shared/api/apiClient', () => ({
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
}));

describe('communicationApi', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should get all posts', async () => {
    apiClient.get.mockResolvedValue({ data: { results: [] } });
    await getPosts();
    expect(apiClient.get).toHaveBeenCalledWith('communication/posts/');
  });

  it('should get a single post', async () => {
    apiClient.get.mockResolvedValue({ data: { id: 1, title: 'Test' } });
    await getPost(1);
    expect(apiClient.get).toHaveBeenCalledWith('communication/posts/1/');
  });

  it('should create a post', async () => {
    apiClient.post.mockResolvedValue({ data: { id: 1, title: 'New' } });
    await createPost({ title: 'New' });
    expect(apiClient.post).toHaveBeenCalledWith('communication/posts/', { title: 'New' });
  });

  it('should update a post', async () => {
    apiClient.put.mockResolvedValue({ data: { id: 1, title: 'Updated' } });
    await updatePost(1, { title: 'Updated' });
    expect(apiClient.put).toHaveBeenCalledWith('communication/posts/1/', { title: 'Updated' });
  });

  it('should delete a post', async () => {
    apiClient.delete.mockResolvedValue({});
    await deletePost(1);
    expect(apiClient.delete).toHaveBeenCalledWith('communication/posts/1/');
  });

  it('should create a comment', async () => {
    apiClient.post.mockResolvedValue({ data: { id: 1, content: 'Good' } });
    await createComment(1, { content: 'Good' });
    expect(apiClient.post).toHaveBeenCalledWith('communication/posts/1/comments/', { content: 'Good' });
  });
});
