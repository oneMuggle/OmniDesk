import { quickActions, fetchWeeklyOverview, fetchDashboardStats } from '../dashboardData';

jest.mock('../../../api/apiClient', () => ({
  get: jest.fn(),
}));
jest.mock('../../../utils/logger', () => ({
  logger: { error: jest.fn() },
}));

import apiClient from '../../../api/apiClient';
import { logger } from '../../../utils/logger';

describe('dashboardData', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('quickActions', () => {
    it('包含 6 项快捷入口', () => {
      expect(quickActions).toHaveLength(6);
    });

    it('每项含 to / title / color,且 to 唯一', () => {
      const tos = quickActions.map(a => a.to);
      expect(new Set(tos).size).toBe(quickActions.length);
      quickActions.forEach(a => {
        expect(a.to).toBeTruthy();
        expect(a.title).toBeTruthy();
        expect(a.color).toBeTruthy();
      });
    });
  });

  describe('fetchWeeklyOverview', () => {
    it('三个 API 全部成功时返回各列表且 errors 为空', async () => {
      // 调用顺序：trials → schedules(IIFE) → bookings
      apiClient.get
        .mockResolvedValueOnce({ data: [{ id: 1, title: '试验A' }] })
        .mockResolvedValueOnce({ data: [{ id: 1, duty_date: '2026-08-15', duty_person: { name: '张三' } }] })
        .mockResolvedValueOnce({ data: [{ id: 1, title: '预约A' }] });

      const result = await fetchWeeklyOverview();

      expect(result.trials).toEqual([{ id: 1, title: '试验A' }]);
      expect(result.schedules).toHaveLength(1);
      expect(result.bookings).toEqual([{ id: 1, title: '预约A' }]);
      expect(result.errors).toEqual({});
      expect(logger.error).not.toHaveBeenCalled();
    });

    it('某个 API 失败时其余仍返回数据且 errors 对应标记', async () => {
      apiClient.get
        .mockRejectedValueOnce(new Error('trials failed'))
        .mockResolvedValueOnce({ data: [{ id: 1, duty_date: '2026-08-15' }] })
        .mockResolvedValueOnce({ data: [{ id: 1, title: '预约A' }] });

      const result = await fetchWeeklyOverview();

      expect(result.trials).toEqual([]);
      expect(result.schedules).toHaveLength(1);
      expect(result.bookings).toHaveLength(1);
      expect(result.errors).toEqual({ trials: true });
      expect(logger.error).toHaveBeenCalledTimes(1);
    });

    it('全部失败时返回空列表 + 全 errors 标记', async () => {
      apiClient.get.mockRejectedValue(new Error('all failed'));

      const result = await fetchWeeklyOverview();

      expect(result.trials).toEqual([]);
      expect(result.schedules).toEqual([]);
      expect(result.bookings).toEqual([]);
      expect(result.errors).toEqual({ trials: true, schedules: true, bookings: true });
      expect(logger.error).toHaveBeenCalledTimes(3);
    });
  });

  describe('fetchDashboardStats', () => {
    it('透传 response.data', async () => {
      const payload = { unread_notifications: 3, projects: { active_count: 5 } };
      apiClient.get.mockResolvedValueOnce({ data: payload });

      const result = await fetchDashboardStats();

      expect(result).toEqual(payload);
      expect(apiClient.get).toHaveBeenCalledWith('dashboard/stats/');
    });
  });
});
