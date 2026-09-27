import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ManageAnnouncementsPage from './ManageAnnouncementsPage';
import apiClient from '../../../shared/api/apiClient';

jest.mock('../../../shared/api/apiClient');

const ROWS = [
  { id: 2, title: 'AI 起草的国庆公告', status: 'draft', published_at: null, created_at: '2026-09-28T02:00:00Z', author: null },
  { id: 1, title: '已发布公告', status: 'published', published_at: '2026-09-20T02:00:00Z', created_at: '2026-09-20T02:00:00Z', author: null },
];

const renderPage = () => render(
  <MemoryRouter>
    <ManageAnnouncementsPage />
  </MemoryRouter>
);

const rowOf = (title) => screen.getByText(title).parentElement;

describe('ManageAnnouncementsPage 草稿与发布', () => {
  beforeEach(() => {
    apiClient.get.mockReset();
    apiClient.post.mockReset();
    apiClient.get.mockResolvedValue({ data: { results: ROWS } });
    window.confirm = jest.fn(() => true);
  });

  it('请求包含草稿,显示状态列;只有草稿有发布按钮', async () => {
    renderPage();
    await screen.findByText('AI 起草的国庆公告');
    expect(apiClient.get).toHaveBeenCalledWith('events/announcements/', { params: { include_drafts: 1 } });
    const draftRow = rowOf('AI 起草的国庆公告');
    expect(within(draftRow).getByText('草稿')).toBeInTheDocument();
    expect(within(draftRow).getByRole('button', { name: '发布' })).toBeInTheDocument();
    const publishedRow = rowOf('已发布公告');
    expect(within(publishedRow).getByText('已发布')).toBeInTheDocument();
    expect(within(publishedRow).queryByRole('button', { name: '发布' })).not.toBeInTheDocument();
  });

  it('确认后调用发布接口并刷新列表', async () => {
    apiClient.post.mockResolvedValue({ data: {} });
    renderPage();
    await screen.findByText('AI 起草的国庆公告');
    fireEvent.click(within(rowOf('AI 起草的国庆公告')).getByRole('button', { name: '发布' }));
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith('events/announcements/2/publish/'));
    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('通知全体用户'));
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledTimes(2));
  });

  it('取消确认时不发布', async () => {
    window.confirm = jest.fn(() => false);
    renderPage();
    await screen.findByText('AI 起草的国庆公告');
    fireEvent.click(within(rowOf('AI 起草的国庆公告')).getByRole('button', { name: '发布' }));
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it('已被他人发布(409)时提示并刷新', async () => {
    apiClient.post.mockRejectedValue(Object.assign(new Error('409'), { response: { status: 409, data: {} } }));
    renderPage();
    await screen.findByText('AI 起草的国庆公告');
    fireEvent.click(within(rowOf('AI 起草的国庆公告')).getByRole('button', { name: '发布' }));
    expect(await screen.findByText('该公告已发布')).toBeInTheDocument();
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledTimes(2));
  });
});
