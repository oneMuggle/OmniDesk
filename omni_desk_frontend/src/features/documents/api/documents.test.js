import documentsApi from './documents';
import apiClient from '../../../shared/api/apiClient';

jest.mock('../../../shared/api/apiClient', () => ({
  get: jest.fn(),
  post: jest.fn(),
}));

describe('documentsApi', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('getDocumentTemplates', () => {
    it('should get all templates without filter', async () => {
      apiClient.get.mockResolvedValue({ data: { results: [] } });

      await documentsApi.getDocumentTemplates();

      expect(apiClient.get).toHaveBeenCalledWith('documents/templates/');
    });

    it('should get templates filtered by project_id', async () => {
      apiClient.get.mockResolvedValue({ data: { results: [] } });

      await documentsApi.getDocumentTemplates(42);

      expect(apiClient.get).toHaveBeenCalledWith('documents/templates/?project_id=42');
    });
  });

  describe('uploadTemplate', () => {
    it('should upload a template with multipart/form-data', async () => {
      const formData = new FormData();
      formData.append('file', new Blob(['test']));
      formData.append('name', 'Test Template');
      apiClient.post.mockResolvedValue({ data: { id: 1, name: 'Test Template' } });

      await documentsApi.uploadTemplate(formData);

      expect(apiClient.post).toHaveBeenCalledWith(
        'documents/templates/upload/',
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
    });
  });

  describe('analyzeDocumentTemplate', () => {
    it('should analyze a template by id', async () => {
      apiClient.post.mockResolvedValue({ data: { status: 'analyzing' } });

      await documentsApi.analyzeDocumentTemplate(5);

      expect(apiClient.post).toHaveBeenCalledWith('documents/templates/5/analyze/');
    });
  });

  describe('generateDocument', () => {
    it('should generate a document from template with blob response', async () => {
      apiClient.post.mockResolvedValue({ data: new Blob() });

      await documentsApi.generateDocument(3, { title: 'Report' });

      expect(apiClient.post).toHaveBeenCalledWith(
        'documents/generate/3',
        { title: 'Report' },
        { responseType: 'blob' }
      );
    });
  });
});
