/**
 * ToolResult 下载卡片渲染测试(Task 13)。
 *
 * 后端 office_generate 工具会返回 tool_result.file_download 字段
 * { filename, download_url }。ToolResult 需渲染 FileDownloadCard,
 * 含文件名 + "下载"按钮;无 file_download 时不渲染。
 */
import { render, screen } from '@testing-library/react';
import ToolResult from '../ToolResult';

beforeAll(() => {
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: jest.fn().mockResolvedValue(undefined) },
    writable: true,
    configurable: true,
  });
});

describe('ToolResult download card', () => {
  test('renders download button when file_download present', () => {
    render(
      <ToolResult
        intent="office_generate"
        result={{
          found: true,
          file_download: {
            filename: '请假单.docx',
            download_url: '/api/smart-assistant/office-download/tok/',
          },
        }}
        sources={null}
      />
    );
    expect(screen.getByText('请假单.docx')).toBeTruthy();
    expect(screen.getByRole('button', { name: /下载/ })).toBeTruthy();
  });

  test('does not render download button without file_download', () => {
    render(<ToolResult intent="schedule_query" result={{ found: true, schedules: [] }} sources={null} />);
    expect(screen.queryByRole('button', { name: /下载/ })).toBeNull();
  });
});