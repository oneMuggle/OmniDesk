/**
 * P0-4:CompliancePage 合规问题列表页测试。
 *
 * 验证断头路由 /control-panel/compliance 补齐后的页面行为:
 * 正常渲染列表 / 空数据 / API 失败兜底。
 */
import { render, screen, waitFor } from '@testing-library/react';
import CompliancePage from '../CompliancePage';
import complianceApi from '../../../../shared/api/compliance';

jest.mock('../../../../shared/api/compliance', () => ({
  __esModule: true,
  default: {
    getAllComplianceIssues: jest.fn(),
  },
}));

const mockIssues = [
  {
    id: 1,
    project_name: '项目A',
    issue_type: '不规范',
    description: '问题描述一',
    location: '第3页',
    severity: '高',
    status: '待处理',
    due_date: '2026-09-01',
  },
  {
    id: 2,
    project_name: '项目B',
    issue_type: '内容缺失',
    description: '问题描述二',
    location: '',
    severity: '低',
    status: '已解决',
    due_date: null,
  },
];

describe('CompliancePage(P0-4)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('渲染 API 返回的合规问题列表', async () => {
    complianceApi.getAllComplianceIssues.mockResolvedValue({
      data: { count: 2, results: mockIssues },
    });

    render(<CompliancePage />);

    await waitFor(() => {
      expect(screen.getByText('项目A')).toBeInTheDocument();
    });
    expect(screen.getByText('项目B')).toBeInTheDocument();
    expect(screen.getByText('问题描述一')).toBeInTheDocument();
    expect(screen.getByText('不规范')).toBeInTheDocument();
    expect(complianceApi.getAllComplianceIssues).toHaveBeenCalledWith({ page: 1, page_size: 10 });
  });

  it('兼容无分页包裹的数组响应', async () => {
    complianceApi.getAllComplianceIssues.mockResolvedValue({ data: mockIssues });

    render(<CompliancePage />);

    await waitFor(() => {
      expect(screen.getByText('项目A')).toBeInTheDocument();
    });
  });

  it('无数据时不渲染任何项目行', async () => {
    complianceApi.getAllComplianceIssues.mockResolvedValue({ data: { count: 0, results: [] } });

    render(<CompliancePage />);

    await waitFor(() => {
      expect(complianceApi.getAllComplianceIssues).toHaveBeenCalled();
    });
    expect(screen.queryByText('项目A')).not.toBeInTheDocument();
  });

  it('API 失败时不崩溃且不渲染数据', async () => {
    complianceApi.getAllComplianceIssues.mockRejectedValue(new Error('network error'));

    render(<CompliancePage />);

    await waitFor(() => {
      expect(complianceApi.getAllComplianceIssues).toHaveBeenCalled();
    });
    expect(screen.queryByText('项目A')).not.toBeInTheDocument();
    // 页面标题仍在(未崩溃)
    expect(screen.getByText('合规问题')).toBeInTheDocument();
  });
});
