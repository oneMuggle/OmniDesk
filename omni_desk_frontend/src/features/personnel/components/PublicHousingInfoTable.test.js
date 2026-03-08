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

 it('renders table with data', () => {
   const mockData = [
     {
       id: 1,
       door_number: '101',
       address: '阳光小区1号楼',
       house_type: '一室一厅',
       area: 50,
       rent: 1500,
       contract_start_date: '2023-01-01',
       contract_end_date: '2024-01-01',
     },
     {
       id: 2,
       door_number: '102',
       address: '阳光小区2号楼',
       house_type: '两室一厅',
       area: 70,
       rent: 2000,
       contract_start_date: '2023-02-01',
       contract_end_date: '2024-02-01',
     },
   ];
   render(<PublicHousingInfoTable data={mockData} />);
   expect(screen.getByText('阳光小区1号楼')).toBeInTheDocument();
   expect(screen.getByText('1500')).toBeInTheDocument();
   expect(screen.getByText('2023-01-01')).toBeInTheDocument();
   expect(screen.getByText('阳光小区2号楼')).toBeInTheDocument();
   expect(screen.getByText('2000')).toBeInTheDocument();
   expect(screen.getByText('2023-02-01')).toBeInTheDocument();
 });
});