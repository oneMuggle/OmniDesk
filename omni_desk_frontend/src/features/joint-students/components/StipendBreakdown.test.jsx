import { render, screen } from '@testing-library/react';
import StipendBreakdown from './StipendBreakdown';

const fixture = {
  base_amount: '6000.00',
  grade_coefficient: '0.80',
  attendance_ratio: '0.50',
  final_amount: '2400.00',
  student_type: 'phd',
  grade: 'B',
};

describe('StipendBreakdown', () => {
  it('展示基本额度 / 系数 / 出勤比 / 最终金额', () => {
    render(<StipendBreakdown record={fixture} />);
    expect(screen.getByText('最终补助金额')).toBeInTheDocument();
    expect(screen.getByText(/基本额度/)).toBeInTheDocument();
    expect(screen.getByText('6000.00 元')).toBeInTheDocument();
    expect(screen.getByText('0.80')).toBeInTheDocument();
    expect(screen.getByText('50%')).toBeInTheDocument();
    // Statistic 在 v5 会渲染为"2,400.00",用正则匹配
    expect(screen.getByText(/2,?400/)).toBeInTheDocument();
    expect(screen.getByText('博士')).toBeInTheDocument();
    expect(screen.getByText('B 档')).toBeInTheDocument();
  });

  it('出勤比超过 1 时按 100% 显示', () => {
    render(<StipendBreakdown record={{ ...fixture, attendance_ratio: '1.50' }} />);
    expect(screen.getByText('100%')).toBeInTheDocument();
  });

  it('硕士 + A 档 文案分支', () => {
    render(
      <StipendBreakdown
        record={{
          base_amount: '3000.00',
          grade_coefficient: '1.00',
          attendance_ratio: '1.00',
          final_amount: '3000.00',
          student_type: 'master',
          grade: 'A',
        }}
      />
    );
    expect(screen.getByText('硕士')).toBeInTheDocument();
    expect(screen.getByText('A 档')).toBeInTheDocument();
    expect(screen.getByText('3000.00 元')).toBeInTheDocument();
    expect(screen.getByText('1.00')).toBeInTheDocument();
  });
});
