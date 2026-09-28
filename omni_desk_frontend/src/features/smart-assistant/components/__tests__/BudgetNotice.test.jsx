import { render, screen } from '@testing-library/react';
import BudgetNotice from '../BudgetNotice';

describe('BudgetNotice', () => {
  it('正常 / 空时不渲染', () => {
    const { rerender } = render(<BudgetNotice budget={null} />);
    expect(screen.queryByTestId('budget-notice')).not.toBeInTheDocument();
    rerender(<BudgetNotice budget={{ state: 'ok' }} />);
    expect(screen.queryByTestId('budget-notice')).not.toBeInTheDocument();
  });

  it('只读 / 停用显示后端文案,缺省时用兜底文案', () => {
    const { rerender } = render(<BudgetNotice budget={{ state: 'readonly', message: '已用 85%' }} />);
    expect(screen.getByTestId('budget-notice')).toHaveTextContent('已用 85%');
    rerender(<BudgetNotice budget={{ state: 'blocked' }} />);
    expect(screen.getByRole('alert')).toHaveTextContent('已用完');
  });
});
