import { render, screen } from '@testing-library/react';
import BankAccountTable from './BankAccountTable';

describe('BankAccountTable', () => {
  it('renders table with correct columns', () => {
    render(<BankAccountTable data={[]} />);
    expect(screen.getByText('开户行')).toBeInTheDocument();
    expect(screen.getByText('账号')).toBeInTheDocument();
    expect(screen.getByText('卡类型')).toBeInTheDocument();
  });
});