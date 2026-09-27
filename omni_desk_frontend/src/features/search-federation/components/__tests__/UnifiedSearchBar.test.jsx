import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import UnifiedSearchBar, { resolveResultRoute } from '../UnifiedSearchBar';
import { unifiedSearch } from '../../api/searchApi';
import { useAuth } from '../../../auth/context/AuthContext';

jest.mock('../../api/searchApi', () => ({
  unifiedSearch: jest.fn(),
}));

jest.mock('../../../auth/context/AuthContext', () => ({
  __esModule: true,
  useAuth: jest.fn(),
}));

const grant = (owned) => (required) => [].concat(required).some((p) => owned.includes(p));

const renderBar = () =>
  render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<UnifiedSearchBar />} />
        <Route path="/memos" element={<div>Memos Page</div>} />
        <Route path="/documents-library" element={<div>Library Page</div>} />
        <Route path="/control-panel/projects" element={<div>Projects Page</div>} />
      </Routes>
    </MemoryRouter>
  );

const typeQuery = async (text) => {
  const input = screen.getByRole('combobox');
  fireEvent.change(input, { target: { value: text } });
  await waitFor(() => expect(unifiedSearch).toHaveBeenCalled());
};

describe('resolveResultRoute', () => {
  it('maps paperless to the in-app library and rejects API urls', () => {
    expect(resolveResultRoute({ source: 'paperless', url: '/api/paperless/documents/1/' })).toBe('/documents-library');
    expect(resolveResultRoute({ source: 'memo', url: '/memos' })).toBe('/memos');
    expect(resolveResultRoute({ source: 'memo', url: '/api/memos/1/' })).toBeNull();
    expect(resolveResultRoute({ source: 'memo', url: 'https://evil.example' })).toBeNull();
    expect(resolveResultRoute(null)).toBeNull();
  });
});

describe('UnifiedSearchBar', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useAuth.mockReturnValue({ hasPermission: grant([]) });
  });

  it('shows labelled internal results and navigates in-app on select', async () => {
    unifiedSearch.mockResolvedValue({
      results: [
        { source: 'memo', id: 1, title: '周报提醒', subtitle: '周五前提交', url: '/memos' },
      ],
      degraded: false,
    });
    renderBar();
    await typeQuery('周报');

    const option = await screen.findByText('周报提醒');
    expect(screen.getByText('备忘录')).toBeInTheDocument();
    expect(screen.getByText('周五前提交')).toBeInTheDocument();

    fireEvent.click(option);
    expect(await screen.findByText('Memos Page')).toBeInTheDocument();
  });

  it('opens paperless results in the document library', async () => {
    unifiedSearch.mockResolvedValue({
      results: [{ source: 'paperless', id: 9, title: '采购合同', url: '/api/paperless/documents/9/' }],
      degraded: false,
    });
    renderBar();
    await typeQuery('合同');
    fireEvent.click(await screen.findByText('采购合同'));
    expect(await screen.findByText('Library Page')).toBeInTheDocument();
  });

  it('disables results whose control-panel page the user cannot open', async () => {
    unifiedSearch.mockResolvedValue({
      results: [{ source: 'project', id: 3, title: '联邦项目', url: '/control-panel/projects' }],
      degraded: false,
    });
    renderBar();
    await typeQuery('联邦');
    fireEvent.click(await screen.findByText('联邦项目'));
    expect(screen.queryByText('Projects Page')).not.toBeInTheDocument();
    expect(screen.getByTitle('无权限打开该页面')).toBeInTheDocument();
  });

  it('shows a degraded hint when paperless is unavailable', async () => {
    unifiedSearch.mockResolvedValue({ results: [], degraded: true });
    renderBar();
    await typeQuery('x');
    expect(await screen.findByText(/文档库服务暂不可用/)).toBeInTheDocument();
  });

  it('renders internal titles as plain text (no HTML injection)', async () => {
    unifiedSearch.mockResolvedValue({
      results: [{ source: 'memo', id: 2, title: '<img src=x onerror=alert(1)>', url: '/memos' }],
      degraded: false,
    });
    renderBar();
    await typeQuery('img');
    expect(await screen.findByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
  });
});
