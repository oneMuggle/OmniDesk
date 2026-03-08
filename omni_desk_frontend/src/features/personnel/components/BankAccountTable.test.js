import { render, screen } from '@testing-library/react';
import BankAccountTable from './BankAccountTable';

describe('BankAccountTable', () => {
  it('renders table with correct columns', () => {
    render(<BankAccountTable data={[]} />);
    expect(screen.getByText('开户行')).toBeInTheDocument();
    expect(screen.getByText('账号')).toBeInTheDocument();
    expect(screen.getByText('卡类型')).toBeInTheDocument();
  });

  it('renders table rows when data is provided', () => {
    const mockData = [
      { id: 1, bank_name: '招商银行', account_number: '**** **** **** 1234', card_type: '储蓄卡' },
      { id: 2, bank_name: '建设银行', account_number: '**** **** **** 5678', card_type: '信用卡' },
    ];
    render(<BankAccountTable data={mockData} />);
    
    // Check for first row data
    expect(screen.getByText('招商银行')).toBeInTheDocument();
    expect(screen.getByText('**** **** **** 1234')).toBeInTheDocument();
    expect(screen.getByText('储蓄卡')).toBeInTheDocument();

    // Check for second row data
    expect(screen.getByText('建设银行')).toBeInTheDocument();
    expect(screen.getByText('**** **** **** 5678')).toBeInTheDocument();
    expect(screen.getByText('信用卡')).toBeInTheDocument();
  });
});