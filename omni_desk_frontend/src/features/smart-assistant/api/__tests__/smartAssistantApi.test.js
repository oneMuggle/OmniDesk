/**
 * smartAssistantApi.submitFeedback 契约测试:
 * PATCH smart-assistant/agent-logs/{logId}/feedback/,body {feedback}
 */
import { submitFeedback } from '../smartAssistantApi';
import apiClient from '../../../../shared/api/apiClient';

jest.mock('../../../../shared/api/apiClient', () => ({
  __esModule: true,
  default: { patch: jest.fn() },
}));

describe('submitFeedback', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('PATCH agent-logs 反馈端点并携带 feedback 载荷', async () => {
    apiClient.patch.mockResolvedValue({ data: { feedback: 'up' } });

    const response = await submitFeedback(42, 'up');

    expect(apiClient.patch).toHaveBeenCalledTimes(1);
    expect(apiClient.patch).toHaveBeenCalledWith(
      'smart-assistant/agent-logs/42/feedback/',
      { feedback: 'up' }
    );
    expect(response.data).toEqual({ feedback: 'up' });
  });

  it('支持 down 反馈与字符串 logId', async () => {
    apiClient.patch.mockResolvedValue({ data: { feedback: 'down' } });

    await submitFeedback('abc-123', 'down');

    expect(apiClient.patch).toHaveBeenCalledWith(
      'smart-assistant/agent-logs/abc-123/feedback/',
      { feedback: 'down' }
    );
  });

  it('API 错误向上抛出供调用方回滚', async () => {
    apiClient.patch.mockRejectedValue(new Error('network'));

    await expect(submitFeedback(1, 'up')).rejects.toThrow('network');
  });
});
