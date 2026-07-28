/**
 * smartAssistantApi.submitFeedback 契约测试:
 * PATCH smart-assistant/agent-logs/{logId}/feedback/,body {feedback}
 *
 * resolveErrorHint 契约测试(输出契约 format_version:1):
 * kind → 友好提示映射,hint 优先,旧事件(无字段)→ undefined
 */
import { submitFeedback, resolveErrorHint, ERROR_KIND_MESSAGES } from '../smartAssistantApi';
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

describe('resolveErrorHint', () => {
  it.each([
    ['no_llm_endpoint', '管理员尚未配置 LLM 服务，请前往「管理后台 → AI 应用」配置端点'],
    ['llm_unavailable', 'LLM 服务暂时不可用，请稍后重试'],
    ['ragflow_unavailable', '知识库服务暂时不可用，本次回答未包含知识库内容'],
    ['rate_limited', '请求过于频繁，请稍后再试'],
    ['internal_error', '服务异常，请稍后重试'],
  ])('kind=%s 映射为对应友好文案', (kind, expected) => {
    expect(resolveErrorHint({ type: 'done', error: true, kind })).toBe(expected);
  });

  it('hint 优先于 kind 映射', () => {
    const event = { type: 'done', error: true, kind: 'rate_limited', hint: '自定义限流提示' };
    expect(resolveErrorHint(event)).toBe('自定义限流提示');
  });

  it('未知 kind 回退 internal_error 文案', () => {
    expect(resolveErrorHint({ type: 'done', error: true, kind: 'something_new' }))
      .toBe(ERROR_KIND_MESSAGES.internal_error);
  });

  it('仅 error:true 无 kind/hint 时回退 internal_error 文案', () => {
    expect(resolveErrorHint({ type: 'done', error: true }))
      .toBe(ERROR_KIND_MESSAGES.internal_error);
  });

  it.each([
    ['旧版 done 事件', { type: 'done' }],
    ['带 format_version 的旧版事件', { type: 'done', format_version: 1 }],
    ['空白 hint 且无 kind', { type: 'done', hint: '   ' }],
    ['undefined', undefined],
    ['null', null],
  ])('%s → undefined(行为与旧版一致)', (_label, event) => {
    expect(resolveErrorHint(event)).toBeUndefined();
  });

  it('hint 首尾空白被修剪', () => {
    expect(resolveErrorHint({ type: 'done', error: true, hint: '  服务维护中  ' }))
      .toBe('服务维护中');
  });
});
