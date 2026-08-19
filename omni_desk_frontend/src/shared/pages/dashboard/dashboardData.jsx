import {
  ExperimentOutlined,
  CalendarOutlined,
  VideoCameraOutlined,
  BellOutlined,
  FileTextOutlined,
  ProjectOutlined,
} from '@ant-design/icons';
import apiClient from '../../api/apiClient';
import { logger } from '../../utils/logger';

// 快捷操作入口(含 JSX 图标,故文件扩展名必须为 .jsx)
export const quickActions = [
  { to: '/announcements', icon: <BellOutlined />, title: '查看公告', color: '#6366f1' },
  { to: '/meeting-rooms', icon: <VideoCameraOutlined />, title: '预约会议室', color: '#10b981' },
  { to: '/trial-schedule', icon: <ExperimentOutlined />, title: '试验日程', color: '#f59e0b' },
  { to: '/shift-schedule', icon: <CalendarOutlined />, title: '排班日程', color: '#3b82f6' },
  { to: '/memos', icon: <FileTextOutlined />, title: '备忘录', color: '#8b5cf6' },
  { to: '/projects', icon: <ProjectOutlined />, title: '项目管理', color: '#ec4899' },
];

// 本周概览：试验 / 排班 / 会议室预约（Promise.allSettled，单项失败不影响其余）
export const fetchWeeklyOverview = async () => {
  const results = await Promise.allSettled([
    apiClient.get('events/trials/this-week/'),
    (async () => {
      const today = new Date();
      const startOfWeek = new Date(today.setDate(today.getDate() - today.getDay() + (today.getDay() === 0 ? -6 : 1)));
      const endOfWeek = new Date(today.setDate(today.getDate() - today.getDay() + 7));
      return apiClient.get('events/schedules/by-date-range/', {
        params: {
          start_date: startOfWeek.toISOString().split('T')[0],
          end_date: endOfWeek.toISOString().split('T')[0]
        }
      });
    })(),
    apiClient.get('meeting-rooms/meeting-room-bookings/this-week/'),
  ]);

  const [trialsResult, schedulesResult, bookingsResult] = results;
  const errors = {};

  if (trialsResult.status === 'rejected') {
    logger.error('Error fetching weekly trials:', trialsResult.reason);
    errors.trials = true;
  }
  if (schedulesResult.status === 'rejected') {
    logger.error('Error fetching weekly schedules:', schedulesResult.reason);
    errors.schedules = true;
  }
  if (bookingsResult.status === 'rejected') {
    logger.error('Error fetching weekly bookings:', bookingsResult.reason);
    errors.bookings = true;
  }

  return {
    trials: trialsResult.status === 'fulfilled' ? trialsResult.value.data : [],
    schedules: schedulesResult.status === 'fulfilled' ? schedulesResult.value.data : [],
    bookings: bookingsResult.status === 'fulfilled' ? bookingsResult.value.data : [],
    errors,
  };
};

// 仪表盘聚合数据
export const fetchDashboardStats = async () => {
  const response = await apiClient.get('dashboard/stats/');
  return response.data;
};
