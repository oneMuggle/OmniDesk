import React from 'react';
import PropTypes from 'prop-types';
import BaseSchedule from './BaseSchedule';
import { fromServerFormat } from '../utils/dateUtils';

const ShiftSchedule = ({
  schedules,
  isGuest,
  onDateClick,
  onEventClick,
  onScheduleSelect = () => {},
  personnel // 接收 personnel prop
}) => {
  // console.log('ScheduleCalendar接收到的排班数据:', schedules); // 添加调试日志
  // console.log('ScheduleCalendar接收到的人员数据:', personnel); // 添加调试日志

  const events = React.useMemo(() => {
    if (!Array.isArray(schedules) || !Array.isArray(personnel)) {
      return [];
    }
    
    return schedules.map(schedule => {
      const title = `${schedule.duty_person?.name || '未知'} (值班) / ${schedule.duty_leader?.name || '未知'} (领导)`;

      return {
        type: 'SCHEDULE',
        id: `schedule-${schedule.id}`, // 为排班事件添加前缀以避免与试验事件ID冲突
        title: title,
        start: fromServerFormat(schedule.duty_date)?.toDate(), // 确保日期格式正确
        allDay: true, // 排班通常是全天事件
        extendedProps: {
          type: 'SCHEDULE',
          duty_person_id: schedule.duty_person?.id, // 仍然保留ID，以防其他地方需要
          duty_leader_id: schedule.duty_leader?.id, // 仍然保留ID，以防其他地方需要
          scheduleDetails: {
            leader: { name: schedule.duty_leader?.name || '未知', contact: schedule.duty_leader?.phone || '' },
            staff: { name: schedule.duty_person?.name || '未知', contact: schedule.duty_person?.phone || '' },
            position: 'N/A', // 假设这些信息不在Schedule模型中
            department: 'N/A', // 假设这些信息不在Schedule模型中
            time: '全天'
          }
        },
        editable: false // 排班在主页面不可编辑
      };
    });
  }, [schedules, personnel, isGuest]);

  return (
    <BaseSchedule
      events={events}
      onDateClick={onDateClick}
      onEventClick={onEventClick}
      editable={false} // 排班在主页面不可编辑
      selectable={false} // 排班在主页面不可选择
      select={onScheduleSelect}
    />
  );
};

ShiftSchedule.propTypes = {
  schedules: PropTypes.array,
  isGuest: PropTypes.bool,
  onDateClick: PropTypes.func,
  onEventClick: PropTypes.func,
  onScheduleSelect: PropTypes.func
};

export default ShiftSchedule;
