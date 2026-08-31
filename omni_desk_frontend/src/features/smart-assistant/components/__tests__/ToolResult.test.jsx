/**
 * ToolResult 聚合卡片渲染测试(P0 修复验证)。
 *
 * 后端多工具链(intent="aggregated_day")返回的 tool_result 是扁平结构
 * {summary, items, total_count, moduleCounts, chain_results},
 * 修复前 ToolResult 读取 result.data 恒为 undefined → 卡片永远显示 Empty。
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ToolResult from '../ToolResult';

beforeAll(() => {
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: jest.fn().mockResolvedValue(undefined) },
    writable: true,
    configurable: true,
  });
});

beforeEach(() => {
  navigator.clipboard.writeText.mockClear();
});

/** 后端 ResultSynthesizer 实际输出的扁平结构 */
const flatAggregatedResult = {
  summary: '共 3 项:排班 2 条、公告 1 条',
  total_count: 3,
  moduleCounts: { 排班: 2, 公告: 1 },
  items: [
    { type: 'schedule_query', module: '排班', data: { duty_date: '2026-07-28', duty_person: '张三' }, sort_key: '2026-07-28' },
    { type: 'schedule_query', module: '排班', data: { duty_date: '2026-07-29', duty_person: '李四' }, sort_key: '2026-07-29' },
    { type: 'announcement_query', module: '公告', data: { title: '系统升级通知' }, sort_key: '9999' },
  ],
  chain_results: [
    { tool: 'schedule_query', found: true },
    { tool: 'announcement_query', found: true },
  ],
};

describe('ToolResult 安全查询结果渲染', () => {
  test('RAG 安全来源 DTO 可渲染文档与计数', () => {
    render(
      <ToolResult
        intent="knowledge_qa"
        result={{ found: true, count: 1 }}
        sources={[{ document: 'IT操作手册.pdf', score: 0.95 }]}
      />
    );

    expect(screen.getByText('IT操作手册.pdf')).toBeInTheDocument();
    expect(screen.getByText(/相似度: 95%/)).toBeInTheDocument();
  });

  test('失败状态 DTO 显示 message 而不是空白', () => {
    render(<ToolResult intent="schedule_query" result={{ found: false, message: '暂无排班记录' }} />);

    expect(screen.getByText('暂无排班记录')).toBeInTheDocument();
  });
});

describe('ToolResult aggregated_day 渲染', () => {
  test('收到扁平 tool_result → 渲染聚合卡片而非 Empty', () => {
    render(<ToolResult intent="aggregated_day" result={flatAggregatedResult} />);

    // 卡片本体渲染(非空分支才有该 testid)
    expect(screen.getByTestId('aggregated-day-card')).toBeInTheDocument();
    // 汇总文本与模块计数标签
    expect(screen.getByText(/共 3 项/)).toBeInTheDocument();
    expect(screen.getByText('排班 2')).toBeInTheDocument();
    expect(screen.getByText('公告 1')).toBeInTheDocument();
    // item 内容(JSON.stringify 渲染)
    expect(screen.getByText(/张三/)).toBeInTheDocument();
    expect(screen.getByText(/系统升级通知/)).toBeInTheDocument();
    // 不应出现空态
    expect(screen.queryByText('未找到相关信息')).not.toBeInTheDocument();
  });

  test('扁平结构按模块分组渲染', () => {
    render(<ToolResult intent="aggregated_day" result={flatAggregatedResult} />);
    // 排班 + 公告 两个分组
    expect(screen.getAllByTestId('module-group')).toHaveLength(2);
  });

  test('兼容 data 包层结构(未来后端演进)', () => {
    render(<ToolResult intent="aggregated_day" result={{ data: flatAggregatedResult }} />);

    expect(screen.getByTestId('aggregated-day-card')).toBeInTheDocument();
    expect(screen.getByText(/共 3 项/)).toBeInTheDocument();
    expect(screen.getByText(/张三/)).toBeInTheDocument();
  });

  test('聚合结果为空时显示空态而非崩溃', () => {
    render(
      <ToolResult
        intent="aggregated_day"
        result={{ summary: '未找到相关信息', items: [], total_count: 0, moduleCounts: {}, chain_results: [] }}
      />
    );

    expect(screen.getByText('未找到相关信息')).toBeInTheDocument();
    expect(screen.queryByTestId('aggregated-day-card')).not.toBeInTheDocument();
  });

  test('兼容 data 包层为空对象时的扁平字段缺失(降级空态)', () => {
    render(<ToolResult intent="aggregated_day" result={{}} />);
    expect(screen.getByText('未找到相关信息')).toBeInTheDocument();
  });

  test('复制按钮序列化扁平结构内容', async () => {
    render(<ToolResult intent="aggregated_day" result={flatAggregatedResult} />);

    fireEvent.click(screen.getByTitle('复制结果'));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledTimes(1);
    });
    const copied = navigator.clipboard.writeText.mock.calls[0][0];
    expect(copied).toContain('共 3 项');
    expect(copied).toContain('张三');
  });
});
