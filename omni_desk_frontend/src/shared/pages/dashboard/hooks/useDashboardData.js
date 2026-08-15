import { useQuery } from '@tanstack/react-query';
import { fetchWeeklyOverview, fetchDashboardStats } from '../dashboardData';

/**
 * 仪表盘聚合数据 hook：本周概览(试验/排班/会议室预约) + 聚合统计。
 * 无 JSX,扩展名 .js 即可。
 */
export const useDashboardData = () => {
  // 本周试验 / 排班 / 会议室预约
  const { data: weeklyData, isLoading: loading } = useQuery({
    queryKey: ['dashboard-weekly-overview'],
    queryFn: fetchWeeklyOverview,
  });

  // 仪表盘聚合数据
  const { data: dashboardStats, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: fetchDashboardStats,
  });

  return {
    weeklyTrials: weeklyData?.trials ?? [],
    weeklySchedules: weeklyData?.schedules ?? [],
    weeklyBookings: weeklyData?.bookings ?? [],
    errors: weeklyData?.errors ?? {},
    loading,
    dashboardStats,
    statsLoading,
  };
};
