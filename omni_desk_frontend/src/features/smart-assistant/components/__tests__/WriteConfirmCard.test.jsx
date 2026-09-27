import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import WriteConfirmCard, { toConfirmMessage } from '../WriteConfirmCard';

jest.mock('../../api/smartAssistantApi', () => ({
  approveConfirmation: jest.fn(),
  rejectConfirmation: jest.fn(),
  revertWriteLog: jest.fn(),
}));

jest.mock('../ToolResult', () => ({
  __esModule: true,
  default: () => <div data-testid="tool-result">下载卡片</div>,
}));

const api = () => require('../../api/smartAssistantApi');

const PREVIEW = {
  action: '更新合规问题状态',
  target: { type: '合规问题', label: '#12 消防通道堵塞' },
  changes: [{ field: 'status', label: '状态', before: '待处理', after: '整改中' }],
  affected_count: 1,
  permission_source: '项目负责人',
  reversible: true,
  risk: 'write',
  items: [],
};

const confirmation = (overrides = {}) => ({ token: 'tok-1', summary: '待确认', preview: PREVIEW, ...overrides });

const httpError = (status, data) => Object.assign(new Error(`HTTP ${status}`), { response: { status, data } });

describe('WriteConfirmCard', () => {
  beforeEach(() => jest.clearAllMocks());

  it('展示预览:对象、改动前后、权限依据、可撤销', () => {
    render(<WriteConfirmCard confirmation={confirmation()} />);
    const card = screen.getByTestId('write-confirm-card');
    expect(card).toHaveTextContent('更新合规问题状态');
    expect(card).toHaveTextContent('#12 消防通道堵塞');
    expect(card).toHaveTextContent('状态：待处理 → 整改中');
    expect(card).toHaveTextContent('权限依据：项目负责人');
    expect(screen.getByText('可撤销')).toBeInTheDocument();
    expect(screen.getByText('写入')).toBeInTheDocument();
  });

  it('确认后显示结果,可撤销', async () => {
    api().approveConfirmation.mockResolvedValue({
      data: { answer: '已将状态改为整改中', reversible: true, write_log_id: 7, tool_result: { found: true } },
    });
    api().revertWriteLog.mockResolvedValue({ data: {} });
    render(<WriteConfirmCard confirmation={confirmation()} />);

    fireEvent.click(screen.getByRole('button', { name: '确认执行' }));
    expect(await screen.findByTestId('write-confirm-result')).toHaveTextContent('已将状态改为整改中');
    expect(api().approveConfirmation).toHaveBeenCalledWith('tok-1');
    expect(screen.queryByRole('button', { name: '确认执行' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /撤\s*销/ }));
    expect(await screen.findByTestId('write-confirm-status')).toHaveTextContent('已撤销');
    expect(api().revertWriteLog).toHaveBeenCalledWith(7);
    expect(screen.queryByRole('button', { name: /撤\s*销/ })).not.toBeInTheDocument();
  });

  it('不可撤销的结果不显示撤销按钮', async () => {
    api().approveConfirmation.mockResolvedValue({ data: { answer: '完成', reversible: false, write_log_id: 3 } });
    render(<WriteConfirmCard confirmation={confirmation()} />);
    fireEvent.click(screen.getByRole('button', { name: '确认执行' }));
    await screen.findByTestId('write-confirm-result');
    expect(screen.queryByRole('button', { name: /撤\s*销/ })).not.toBeInTheDocument();
  });

  it('撤销冲突时显示原因,仍可再试', async () => {
    api().approveConfirmation.mockResolvedValue({ data: { answer: '完成', reversible: true, write_log_id: 9 } });
    api().revertWriteLog.mockRejectedValue(httpError(409, { detail: '状态已被他人修改，无法撤销' }));
    render(<WriteConfirmCard confirmation={confirmation()} />);
    fireEvent.click(screen.getByRole('button', { name: '确认执行' }));
    fireEvent.click(await screen.findByRole('button', { name: /撤\s*销/ }));
    expect(await screen.findByTestId('write-confirm-error')).toHaveTextContent('状态已被他人修改');
    expect(screen.getByRole('button', { name: /撤\s*销/ })).toBeInTheDocument();
  });

  it('取消后不再显示按钮', async () => {
    api().rejectConfirmation.mockResolvedValue({ data: { rejected: true } });
    render(<WriteConfirmCard confirmation={confirmation()} />);
    fireEvent.click(screen.getByRole('button', { name: /取\s*消/ }));
    expect(await screen.findByTestId('write-confirm-status')).toHaveTextContent('已取消');
    expect(api().rejectConfirmation).toHaveBeenCalledWith('tok-1');
    expect(api().approveConfirmation).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: '确认执行' })).not.toBeInTheDocument();
  });

  it.each([
    [410, { code: 'confirmation_expired' }, '确认已过期'],
    [409, { detail: '该时段已被预约', code: 'booking_conflict' }, '该时段已被预约'],
    [403, { code: 'confirmation_user_mismatch' }, '只能由发起人确认'],
  ])('服务端返回 %s 时显示原因且不能再次确认', async (status, data, text) => {
    api().approveConfirmation.mockRejectedValue(httpError(status, data));
    render(<WriteConfirmCard confirmation={confirmation()} />);
    fireEvent.click(screen.getByRole('button', { name: '确认执行' }));
    expect(await screen.findByTestId('write-confirm-error')).toHaveTextContent(text);
    expect(screen.queryByRole('button', { name: '确认执行' })).not.toBeInTheDocument();
  });

  it('请求未到达服务端时允许重试', async () => {
    api().approveConfirmation.mockRejectedValueOnce(new Error('Network Error'));
    render(<WriteConfirmCard confirmation={confirmation()} />);
    fireEvent.click(screen.getByRole('button', { name: '确认执行' }));
    expect(await screen.findByTestId('write-confirm-error')).toHaveTextContent('Network Error');
    await waitFor(() => expect(screen.getByRole('button', { name: '确认执行' })).not.toBeDisabled());
  });

  it('删除类操作显示红色标签;没有预览时回退到摘要', () => {
    const { unmount } = render(
      <WriteConfirmCard confirmation={confirmation({ preview: { ...PREVIEW, risk: 'destructive', reversible: false } })} />
    );
    expect(screen.getByText('删除')).toBeInTheDocument();
    expect(screen.getByText('不可撤销')).toBeInTheDocument();
    unmount();

    render(<WriteConfirmCard confirmation={confirmation({ preview: null, summary: '请确认工具操作' })} />);
    expect(screen.getByTestId('write-confirm-card')).toHaveTextContent('请确认工具操作');
    expect(screen.queryByText('写入')).not.toBeInTheDocument();
  });

  it('文档生成结果展示下载卡片', async () => {
    api().approveConfirmation.mockResolvedValue({
      data: { answer: '文档已生成', tool_used: 'office_generate', tool_result: { found: true, file_download: { token: 'f' } } },
    });
    render(<WriteConfirmCard confirmation={confirmation({ preview: null })} />);
    fireEvent.click(screen.getByRole('button', { name: '确认执行' }));
    expect(await screen.findByTestId('tool-result')).toBeInTheDocument();
  });

  it('toConfirmMessage 转换 confirmation 事件,缺 token 返回 null', () => {
    expect(toConfirmMessage({ type: 'confirmation' })).toBeNull();
    const message = toConfirmMessage(
      { confirmation_token: 'abc', answer: '请确认', draft: { summary: 's', preview: PREVIEW } },
      'compliance_issue_update_status'
    );
    expect(message).toEqual({
      id: 'confirm-abc',
      type: 'write_confirm',
      role: 'assistant',
      confirmation: { token: 'abc', summary: 's', answer: '请确认', preview: PREVIEW, toolUsed: 'compliance_issue_update_status' },
    });
  });
});
