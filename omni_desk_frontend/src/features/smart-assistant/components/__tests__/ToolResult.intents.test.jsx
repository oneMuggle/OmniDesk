/**
 * ToolResult 注册中心 intent 渲染冒烟测试(R3-D2 新增)。
 *
 * 遍历 TOOL_RESULT_REGISTRY 中每个 intent,用示例数据渲染对应卡片,
 * 断言标题 Tag 出现且不崩溃 —— 补齐既有测试未覆盖的 intent 分支回归守卫
 * (aggregated_day / download 已有独立测试)。
 */
import { render, screen } from '@testing-library/react';
import ToolResult from '../ToolResult';
import TOOL_RESULT_REGISTRY from '../toolResults/registry';

/** 每个 intent 的渲染示例数据;title = 期望出现的卡片标题 Tag 文本,testId 优先(aggregated_day) */
const INTENT_CASES = {
  aggregated_day: {
    testId: 'aggregated-day-card',
    result: {
      summary: '共 1 项',
      total_count: 1,
      moduleCounts: { 排班: 1 },
      items: [{ type: 'schedule_query', module: '排班', data: { duty_date: '2026-07-28', duty_person: '张三' }, sort_key: '2026-07-28' }],
      chain_results: [{ tool: 'schedule_query', found: true }],
    },
  },
  schedule_query: {
    title: '排班信息',
    result: { found: true, schedules: [{ duty_date: '2026-07-28', duty_person: '张三', duty_leader: '李四' }] },
  },
  personnel_query: {
    title: '人员信息',
    result: { found: true, personnel: [{ name: '张三', department: '技术部', position: '工程师', status: '在职', phone_number: '123456' }] },
  },
  knowledge_qa: {
    title: '引用来源',
    sources: [{ document: '测试文档', score: 0.85 }],
    result: { found: true },
  },
  document_search: {
    title: '文档搜索',
    result: { found: true, documents: [{ type: '文档', title: '测试文档' }] },
  },
  event_query: {
    title: '事件/日程',
    result: {
      found: true,
      date: '2026-07-28',
      schedules: [{ duty_person: '张三', duty_leader: '李四' }],
      holidays: [{ name: '元旦', start_date: '2026-01-01', end_date: '2026-01-03' }],
    },
  },
  memo_query: {
    title: '备忘录',
    result: { found: true, memos: [{ title: '待办', content: '内容', user: '张三', is_completed: false, reminder_time: '无提醒', created_at: '2026-07-28' }] },
  },
  project_status: {
    title: '项目信息',
    result: { found: true, projects: [{ name: '项目A', manager: '张三', status: '进行中', description: '描述', start_date: '2026-01-01', end_date: '2026-12-31' }] },
  },
  announcement_query: {
    title: '公司公告',
    result: { found: true, posts: [{ title: '公告', author: '张三', created_at: '2026-07-28', content: '内容' }] },
  },
  compliance_query: {
    title: '合规问题',
    result: { found: true, issues: [{ issue_type: '未授权', description: '描述', status: '未解决', severity: '高', project: '项目A', due_date: '2026-08-01' }] },
  },
  external_link_query: {
    title: '内网外链',
    result: { found: true, links: [{ name: 'OA系统', url: 'http://oa', category: '办公', sso_enabled: false }] },
  },
  news_search: {
    title: '新闻/通知',
    result: { found: true, articles: [{ title: '新闻', news_type: '通知', publication_date: '2026-07-28', personnel: '张三' }] },
  },
};

describe('ToolResult 注册中心 intent 渲染冒烟测试', () => {
  test('注册中心覆盖 12 个 intent', () => {
    expect(Object.keys(TOOL_RESULT_REGISTRY).sort()).toEqual(Object.keys(INTENT_CASES).sort());
  });

  test.each(Object.entries(INTENT_CASES))('%s 渲染对应卡片', (intent, { result, sources, title, testId }) => {
    render(<ToolResult intent={intent} result={result} sources={sources} />);
    if (testId) {
      expect(screen.getByTestId(testId)).toBeInTheDocument();
    } else {
      expect(screen.getByText(title)).toBeInTheDocument();
    }
  });

  test('intent 匹配但守卫不通过时落回未找到兜底', () => {
    render(<ToolResult intent="schedule_query" result={{ found: false, message: '未找到排班' }} />);
    expect(screen.getByText('未找到排班')).toBeInTheDocument();
  });
});
