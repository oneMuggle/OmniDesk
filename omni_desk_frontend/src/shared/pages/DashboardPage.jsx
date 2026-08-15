import { Typography } from 'antd';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import 'dayjs/locale/zh-cn';
import { useDashboardData } from './dashboard/hooks/useDashboardData';
import DashboardHeader from './dashboard/DashboardHeader';
import StatSummaryCards from './dashboard/StatSummaryCards';
import MemosAndAnnouncements from './dashboard/MemosAndAnnouncements';
import QuickStatsRow from './dashboard/QuickStatsRow';
import WeeklyOverview from './dashboard/WeeklyOverview';
import './DashboardPage.css';

// dayjs relativeTime/zh-cn 已由应用入口 index.jsx 全局注册;
// 此处保留原页面独立注册作双保险(幂等),子组件 fromNow() 在直接渲染时亦可用
dayjs.extend(relativeTime);
dayjs.locale('zh-cn');

const { Text } = Typography;

const DashboardPage = () => {
  const {
    weeklyTrials,
    weeklySchedules,
    weeklyBookings,
    errors,
    loading,
    dashboardStats,
    statsLoading,
  } = useDashboardData();

  return (
    <div className="dashboard-page-container">
      <DashboardHeader />
      <StatSummaryCards dashboardStats={dashboardStats} statsLoading={statsLoading} />
      <MemosAndAnnouncements dashboardStats={dashboardStats} statsLoading={statsLoading} />
      <QuickStatsRow
        weeklyTrials={weeklyTrials}
        weeklySchedules={weeklySchedules}
        weeklyBookings={weeklyBookings}
      />
      <WeeklyOverview
        weeklyTrials={weeklyTrials}
        weeklySchedules={weeklySchedules}
        weeklyBookings={weeklyBookings}
        loading={loading}
        errors={errors}
      />
      <div className="welcome-page-footer">
        <Text type="secondary">如有任何疑问，请联系管理员。</Text>
      </div>
    </div>
  );
};

export default DashboardPage;
