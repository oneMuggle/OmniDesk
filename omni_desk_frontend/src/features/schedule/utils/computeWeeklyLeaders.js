import dayjs from 'dayjs';

/**
 * 从排班数据中按周提取值班领导信息。
 * @param {Array} schedules - 排班数据数组
 * @param {Object} calendarViewInfo - 日历视图信息，包含 start 和 end
 * @returns {Array} 按周分组的值班领导数据
 */
export const computeWeeklyLeaders = (schedules, calendarViewInfo) => {
  if (!calendarViewInfo || !schedules || schedules.length === 0) {
    return [];
  }

  const start = dayjs(calendarViewInfo.start);
  const end = dayjs(calendarViewInfo.end);
  const leadersByWeek = {};

  schedules.forEach(schedule => {
    const scheduleDate = dayjs(schedule.duty_date);
    if (scheduleDate.isBetween(start, end, 'day', '[]')) {
      const week = scheduleDate.week();
      if (!leadersByWeek[week]) {
        leadersByWeek[week] = {
          id: week,
          start: scheduleDate.clone().startOf('week').format('YYYY-MM-DD'),
          leaders: [],
          schedules: []
        };
      }
      if (schedule.duty_leader && !leadersByWeek[week].leaders.some(l => l.id === schedule.duty_leader.id)) {
        leadersByWeek[week].leaders.push(schedule.duty_leader);
      }
      leadersByWeek[week].schedules.push(schedule);
    }
  });

  return Object.values(leadersByWeek).sort((a, b) => a.id - b.id);
};
