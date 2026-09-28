/**
 * StatsPage 运营统计页测试（方案 5.6 / S0 补充指标）
 *
 * 覆盖:
 * - 回答成功率、LLM 调用成功率、P50 / P95 卡片
 * - 按模型分列表格
 * - 每日趋势里的回答成功率与 P95
 * - 没有数据时比例显示「—」而不是 0%
 * - 切换时间范围重新请求
 */
import { fireEvent, render, screen, within } from '@testing-library/react';
import StatsPage from '../StatsPage';
import { getStatsDaily, getStatsOverview } from '../../api/smartAssistantApi';

jest.mock('../../api/smartAssistantApi', () => ({
  getStatsOverview: jest.fn(),
  getStatsDaily: jest.fn(),
}));

const OVERVIEW = {
  period_days: 30,
  total_conversations: 12,
  active_users: 3,
  unrecognized: 1,
  intent_breakdown: { memo_query: 5 },
  tool_breakdown: { memo_query: 5 },
  top_questions: [{ intent: 'memo_query', count: 5 }],
  conversation_count: 10,
  answer_failures: 1,
  answer_success_rate: 90,
  p50_response_time_ms: 820,
  p95_response_time_ms: 4100,
  llm_calls: 38,
  llm_failed_calls: 2,
  llm_call_success_rate: 95,
  by_model: [
    {
      model: 'qwen2.5-72b',
      conversations: 8,
      answer_success_rate: 100,
      avg_response_time_ms: 900,
      p95_response_time_ms: 2100,
      total_tokens: 12000,
    },
    {
      model: '未记录',
      conversations: 2,
      answer_success_rate: 50,
      avg_response_time_ms: 3000,
      p95_response_time_ms: 5000,
      total_tokens: 0,
    },
  ],
};

const DAILY = {
  daily_stats: [
    {
      date: '2026-09-27',
      conversations: 4,
      tool_calls: 2,
      answer_success_rate: 75,
      p95_response_time_ms: 3300,
    },
    {
      date: '2026-09-26',
      conversations: 0,
      tool_calls: 0,
      answer_success_rate: null,
      p95_response_time_ms: 0,
    },
  ],
};

describe('StatsPage', () => {
  beforeEach(() => {
    getStatsOverview.mockResolvedValue({ data: OVERVIEW });
    getStatsDaily.mockResolvedValue({ data: DAILY });
  });

  afterEach(() => jest.clearAllMocks());

  it('展示回答成功率、LLM 调用成功率与延迟分位', async () => {
    render(<StatsPage />);
    expect(await screen.findByText('响应时间 P95', {}, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.getByText('LLM 调用成功率')).toBeInTheDocument();
    expect(screen.getByText('90%')).toBeInTheDocument();
    expect(screen.getByText('95%')).toBeInTheDocument();
    expect(screen.getByText('响应时间 P50')).toBeInTheDocument();
    expect(screen.getByText('820')).toBeInTheDocument();
    expect(screen.getByText('4,100')).toBeInTheDocument();
  });

  it('按模型分列', async () => {
    render(<StatsPage />);
    const row = await screen.findByRole('row', { name: /qwen2\.5-72b/ }, { timeout: 4000 });
    expect(within(row).getByText('100%')).toBeInTheDocument();
    expect(within(row).getByText('900 ms')).toBeInTheDocument();
    expect(within(row).getByText('2100 ms')).toBeInTheDocument();
    expect(screen.getByText('未记录')).toBeInTheDocument();
  });

  it('每日趋势带成功率与 P95，没有对话的日期显示「—」', async () => {
    render(<StatsPage />);
    const row = await screen.findByRole('row', { name: /2026-09-27/ }, { timeout: 4000 });
    expect(within(row).getByText('75%')).toBeInTheDocument();
    expect(within(row).getByText('3300 ms')).toBeInTheDocument();
    const empty = screen.getByRole('row', { name: /2026-09-26/ });
    expect(within(empty).getByText('—')).toBeInTheDocument();
  });

  it('窗口内没有数据时比例显示「—」', async () => {
    getStatsOverview.mockResolvedValue({
      data: {
        ...OVERVIEW,
        answer_success_rate: null,
        llm_call_success_rate: null,
        by_model: [],
      },
    });
    render(<StatsPage />);
    await screen.findByText('响应时间 P95', {}, { timeout: 4000 });
    // 两张比例卡都显示「—」（每日趋势里 09-26 还有一个）
    expect(screen.getAllByText('—')).toHaveLength(3);
    expect(screen.queryByText('90%')).not.toBeInTheDocument();
  });

  it('切换时间范围重新请求', async () => {
    render(<StatsPage />);
    await screen.findByText('响应时间 P95', {}, { timeout: 4000 });
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '7' } });
    await screen.findByText('响应时间 P95', {}, { timeout: 4000 });
    expect(getStatsOverview).toHaveBeenLastCalledWith(7);
    expect(getStatsDaily).toHaveBeenLastCalledWith(7);
  });
});
