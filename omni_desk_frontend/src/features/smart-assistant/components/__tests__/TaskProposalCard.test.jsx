import { render, screen, fireEvent } from '@testing-library/react';
import TaskProposalCard from '../TaskProposalCard';

const proposal = { objective: '调研并撰写报告', mode: 'agent_task' };

describe('TaskProposalCard', () => {
  it('展示任务目标,两个按钮分别回调', () => {
    const onCreate = jest.fn();
    const onAnswerDirectly = jest.fn();
    render(<TaskProposalCard proposal={proposal} onCreate={onCreate} onAnswerDirectly={onAnswerDirectly} />);

    expect(screen.getByText('调研并撰写报告')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '创建协作任务' }));
    fireEvent.click(screen.getByRole('button', { name: '直接回答' }));
    expect(onCreate).toHaveBeenCalledTimes(1);
    expect(onAnswerDirectly).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId('task-proposal-status')).not.toBeInTheDocument();
  });

  it.each([
    ['created', '已创建协作任务'],
    ['answered', '已改为直接回答'],
  ])('状态 %s 时按钮锁定并显示提示', (status, text) => {
    render(<TaskProposalCard proposal={proposal} status={status} onCreate={jest.fn()} onAnswerDirectly={jest.fn()} />);
    expect(screen.getByRole('button', { name: '创建协作任务' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '直接回答' })).toBeDisabled();
    expect(screen.getByTestId('task-proposal-status')).toHaveTextContent(text);
  });

  it('失败状态允许重试', () => {
    render(<TaskProposalCard proposal={proposal} status="error" onCreate={jest.fn()} onAnswerDirectly={jest.fn()} />);
    expect(screen.getByRole('button', { name: '创建协作任务' })).not.toBeDisabled();
    expect(screen.getByTestId('task-proposal-status')).toHaveTextContent('任务创建失败');
  });

  it('没有任务目标时不渲染', () => {
    const { container } = render(
      <TaskProposalCard proposal={{ objective: '' }} onCreate={jest.fn()} onAnswerDirectly={jest.fn()} />
    );
    expect(container).toBeEmptyDOMElement();
  });
});
