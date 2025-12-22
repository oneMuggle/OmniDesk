import { render, screen } from '@testing-library/react';
import PublicHousingInfoTable from './PublicHousingInfoTable';

describe('PublicHousingInfoTable', () => {
  it('renders table with correct columns', () => {
    render(<PublicHousingInfoTable data={[]} />);
    expect(screen.getByText('门牌号')).toBeInTheDocument();
    expect(screen.getByText('房屋地址')).toBeInTheDocument();
    expect(screen.getByText('房屋类型')).toBeInTheDocument();
    expect(screen.getByText('房屋面积')).toBeInTheDocument();
  });
});