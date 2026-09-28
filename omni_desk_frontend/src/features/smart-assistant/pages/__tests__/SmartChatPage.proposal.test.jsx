/**
 * S4-1:从数字员工通知进入智能助手(/smart-assistant?proposal=<id>),显示确认卡并确认 / 取消。
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ConfigProvider } from 'antd';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import SmartChatPage from '../SmartChatPage';

jest.mock('../../api/smartAssistantApi', () => ({
  ...jest.requireActual('../../api/smartAssistantApi'),
  sendSmartChatStream: jest.fn(),
  getSessions: jest.fn().mockResolvedValue({ data: { results: [] } }),
  getProposal: jest.fn(),
  approveProposal: jest.fn(),
  rejectProposal: jest.fn(),
  approveConfirmation: jest.fn(),
  revertWriteLog: jest.fn(),
}));

const api = () => require('../../api/smartAssistantApi');

beforeAll(() => {
  Element.prototype.scrollIntoView = jest.fn();
});

beforeEach(() => {
  jest.clearAllMocks();
});

const PROPOSAL = {
  id: 7,
  profile_name: '合规专员',
  kind: 'compliance_suggestion',
  title: '保存整改建议：S4 项目 · 内容缺失',
  status: 'pending',
  result_message: null,
  preview: {
    action: '保存整改建议',
    target: { type: '合规问题', label: 'S4 项目 · 内容缺失' },
    changes: [{ field: 'title', label: '备忘录标题', before: null, after: '整改：S4 项目 · 内容缺失' }],
    affected_count: 1,
    affected_label: '条备忘录',
    permission_source: '本人负责的项目',
    reversible: true,
    risk: 'write',
    items: ['- 补签原始记录'],
    warnings: ['建议由 AI 生成，仅供参考，请结合实际核对。'],
  },
};

const Search = () => <div data-testid="search">{useLocation().search}</div>;

const renderAt = (url) => render(
  <ConfigProvider>
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/smart-assistant" element={<><SmartChatPage /><Search /></>} />
      </Routes>
    </MemoryRouter>
  </ConfigProvider>
);

describe('SmartChatPage 数字员工待确认事项', () => {
  it('按链接参数拉取事项并显示确认卡,随后去掉参数', async () => {
    api().getProposal.mockResolvedValue({ data: PROPOSAL });
    renderAt('/smart-assistant?proposal=7');
    expect(await screen.findByTestId('write-confirm-card', {}, { timeout: 4000 })).toBeInTheDocument();
    expect(api().getProposal).toHaveBeenCalledWith('7');
    expect(screen.getByTestId('write-confirm-source')).toHaveTextContent('来自数字员工：合规专员');
    expect(screen.getByText('S4 项目 · 内容缺失')).toBeInTheDocument();
    expect(screen.getByText('- 补签原始记录')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('search').textContent).toBe(''));
  });

  it('确认执行调用 proposals 接口并可撤销', async () => {
    api().getProposal.mockResolvedValue({ data: PROPOSAL });
    api().approveProposal.mockResolvedValue({
      data: { answer: '整改建议已存为你的备忘录。', confirmed: true, write_log_id: 12, reversible: true },
    });
    renderAt('/smart-assistant?proposal=7');
    fireEvent.click(await screen.findByRole('button', { name: '确认执行' }, { timeout: 4000 }));
    expect(await screen.findByText('整改建议已存为你的备忘录。')).toBeInTheDocument();
    expect(api().approveProposal).toHaveBeenCalledWith(7);
    expect(api().approveConfirmation).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /撤\s*销/ })).toBeInTheDocument();
  });

  it('取消调用 rejectProposal', async () => {
    api().getProposal.mockResolvedValue({ data: PROPOSAL });
    api().rejectProposal.mockResolvedValue({ data: { cancelled: true } });
    renderAt('/smart-assistant?proposal=7');
    fireEvent.click(await screen.findByRole('button', { name: /取\s*消/ }, { timeout: 4000 }));
    expect(await screen.findByText('已取消，未做任何修改')).toBeInTheDocument();
    expect(api().rejectProposal).toHaveBeenCalledWith(7);
  });

  it('已过期的事项不显示确认按钮', async () => {
    api().getProposal.mockResolvedValue({ data: { ...PROPOSAL, status: 'expired' } });
    renderAt('/smart-assistant?proposal=7');
    expect(await screen.findByText('该事项已过期', {}, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '确认执行' })).not.toBeInTheDocument();
  });

  it('事项不存在时不插入卡片', async () => {
    api().getProposal.mockRejectedValue({ response: { status: 404 } });
    renderAt('/smart-assistant?proposal=99');
    expect(await screen.findByText('待确认事项不存在或无权查看', {}, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.queryByTestId('write-confirm-card')).not.toBeInTheDocument();
  });

  it('没有参数时不请求', () => {
    renderAt('/smart-assistant');
    expect(api().getProposal).not.toHaveBeenCalled();
  });
});
