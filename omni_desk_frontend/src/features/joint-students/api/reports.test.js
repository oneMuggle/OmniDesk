import * as api from './reports';
import client from './client';

jest.mock('./client', () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), patch: jest.fn() },
}));

describe('reports API', () => {
  beforeEach(() => jest.clearAllMocks());

  it('list/get/create/update report 使用正确路径', () => {
    api.listReports({ status: 'submitted' });
    api.getReport(3);
    api.createReport({ year: 2026, month: 8 });
    api.updateReport(3, { work_progress: '完成' });
    expect(client.get).toHaveBeenNthCalledWith(1, 'reports/', { params: { status: 'submitted' } });
    expect(client.get).toHaveBeenNthCalledWith(2, 'reports/3/');
    expect(client.post).toHaveBeenCalledWith('reports/', { year: 2026, month: 8 });
    expect(client.patch).toHaveBeenCalledWith('reports/3/', { work_progress: '完成' });
  });

  it('submit/approve/reject 使用状态动作', () => {
    api.submitReport(3);
    api.approveReport(3);
    api.rejectReport(3, '请补充进展');
    expect(client.post).toHaveBeenNthCalledWith(1, 'reports/3/submit/');
    expect(client.post).toHaveBeenNthCalledWith(2, 'reports/3/approve/');
    expect(client.post).toHaveBeenNthCalledWith(3, 'reports/3/reject/', {
      reviewer_comment: '请补充进展',
    });
  });
});
