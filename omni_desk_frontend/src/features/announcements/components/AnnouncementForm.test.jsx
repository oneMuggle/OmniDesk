import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import AnnouncementForm from './AnnouncementForm';
import apiClient from '../../../shared/api/apiClient';

jest.mock('../../../shared/api/apiClient');

// 富文本编辑器依赖 quill,测试中以轻量 stub 替代,仅回显 value
jest.mock('../../../shared/components/RichTextEditor', () => {
  const { forwardRef: mockForwardRef } = require('react');
  return {
    __esModule: true,
    default: mockForwardRef((props, ref) => (
      <div data-testid="rich-text-editor" ref={ref}>
        {props.value}
      </div>
    )),
  };
});

const renderAt = (initialPath) =>
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route
          path="/control-panel/announcements/create"
          element={<AnnouncementForm />}
        />
        <Route
          path="/control-panel/announcements/:announcementId/edit"
          element={<AnnouncementForm />}
        />
      </Routes>
    </MemoryRouter>
  );

describe('AnnouncementForm', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('编辑模式正确读取 announcementId 路由参数并加载公告数据', async () => {
    apiClient.get.mockResolvedValue({
      data: { title: '测试公告标题', content: '测试公告内容' },
    });

    renderAt('/control-panel/announcements/42/edit');

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('events/announcements/42/');
    });

    expect(await screen.findByText('编辑公告')).toBeInTheDocument();
    expect(await screen.findByDisplayValue('测试公告标题')).toBeInTheDocument();
    expect(screen.getByTestId('rich-text-editor')).toHaveTextContent('测试公告内容');
  });

  it('创建模式(无 announcementId)不请求公告详情', async () => {
    renderAt('/control-panel/announcements/create');

    expect(await screen.findByText('发布新公告')).toBeInTheDocument();
    expect(apiClient.get).not.toHaveBeenCalled();
  });
});
