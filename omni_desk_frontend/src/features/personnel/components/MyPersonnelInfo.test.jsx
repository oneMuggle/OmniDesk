/**
 * P5-2:MyPersonnelInfo 组件最小化测试 — 目标把覆盖率从 22.92% 推回 ≥23%
 */
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import MyPersonnelInfo from './MyPersonnelInfo';
import { getMyPersonnel } from '../api/personnelApi';

jest.mock('../api/personnelApi');

const mockData = {
  id: 1,
  name: '张三',
  date_of_birth: '1990-01-15',
  phone_number: '13800000000',
  address: '某地址',
  department: '研发部',
  position: { name: '工程师' },
  status: 'active',
};

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <MyPersonnelInfo />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

describe('MyPersonnelInfo', () => {
  it('renders loading state initially', () => {
    getMyPersonnel.mockImplementation(() => new Promise(() => {}));
    renderWithProviders();
    expect(screen.getByText(/我的信息/i)).toBeInTheDocument();
  });

  it('renders personnel fields when data loaded', async () => {
    getMyPersonnel.mockResolvedValue(mockData);
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByDisplayValue('张三')).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue('13800000000')).toBeInTheDocument();
  });

  it('shows no-personnel message on 404', async () => {
    const err = new Error('Not Found');
    err.response = { status: 404 };
    getMyPersonnel.mockRejectedValue(err);
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByText(/尚未关联人员档案/i)).toBeInTheDocument();
    });
  });
});
