import { processText } from './officeAssistantApi';
import apiClient from '../../../shared/api/apiClient';

jest.mock('../../../shared/api/apiClient', () => ({
  post: jest.fn(),
}));

describe('officeAssistantApi', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should process text with proofread action', async () => {
    apiClient.post.mockResolvedValue({ data: { result: 'corrected text' } });
    const result = await processText('Hello worl', 'proofread');
    expect(apiClient.post).toHaveBeenCalledWith('office_assistant/process/', {
      text: 'Hello worl',
      action: 'proofread',
    });
    expect(result.data.result).toBe('corrected text');
  });

  it('should process text with translate action', async () => {
    apiClient.post.mockResolvedValue({ data: { result: '翻译文本' } });
    const result = await processText('Hello', 'translate');
    expect(apiClient.post).toHaveBeenCalledWith('office_assistant/process/', {
      text: 'Hello',
      action: 'translate',
    });
    expect(result.data.result).toBe('翻译文本');
  });

  it('should process text with polish action', async () => {
    apiClient.post.mockResolvedValue({ data: { result: 'Polished text' } });
    const result = await processText('Basic text', 'polish');
    expect(apiClient.post).toHaveBeenCalledWith('office_assistant/process/', {
      text: 'Basic text',
      action: 'polish',
    });
    expect(result.data.result).toBe('Polished text');
  });
});
