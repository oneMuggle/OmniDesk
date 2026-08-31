import { render, screen } from '@testing-library/react';
import { ConfigProvider } from 'antd';
import FinalAnswerCard from './FinalAnswerCard';

jest.mock('./AgentCard', () => function MockAgentCard({ content }) { return <div>{content}</div>; });

describe('FinalAnswerCard', () => {
  it('partial dict/list/subtask outputs render safe text rather than object children', () => {
    render(
      <ConfigProvider>
        <FinalAnswerCard
          agent="Supervisor"
          status="partial"
          finalOutput={{
            summary: { nested: 'summary' },
            subtasks: [{ id: 's1', output: { answer: 'done' } }],
          }}
        />
      </ConfigProvider>
    );

    const output = screen.getByTestId('agent-final-output');
    expect(output).toHaveTextContent('nested: summary');
    expect(output).toHaveTextContent('subtasks:');
    expect(output).not.toHaveTextContent('[object Object]');
  });
});
