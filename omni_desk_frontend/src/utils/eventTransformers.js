import { fromServerFormat } from './dateUtils';
import './../types/schedule'; // Import the typedefs

/**
 * 将后端排班数据转换为 ScheduleEvent 格式
 * @param {Array} schedules - 后端排班数据
 * @param {Array} personnel - 人员数据
 * @returns {Array<ScheduleEvent>} 转换后的 ScheduleEvent 数组
 */
export const transformScheduleToEvents = (schedules, personnel) => {
  if (!Array.isArray(schedules) || !Array.isArray(personnel)) {
    return [];
  }

  return schedules.map(schedule => {
    const duty_person = personnel.find(p => p.id === schedule.duty_person) || { name: '未知', phone: '' };
    const duty_leader = personnel.find(p => p.id === schedule.duty_leader) || { name: '未知', phone: '' };

    const start = fromServerFormat(schedule.duty_date)?.toDate();

    return {
      type: 'SCHEDULE',
      id: `schedule-${schedule.id}`,
      title: `${duty_person.name} (值班) / ${duty_leader.name} (领导)`, // 保持原始 title，以便在需要时作为备用
      start: start,
      end: start, // 排班通常是全天事件，开始和结束时间相同
      allDay: true,
      extendedProps: {
        duty_person_id: schedule.duty_person,
        duty_leader_id: schedule.duty_leader,
        duty_person_name: duty_person.name, // 添加值班人员名称
        duty_leader_name: duty_leader.name, // 添加值班领导名称
        scheduleDetails: {
          duty_person: duty_person,
          duty_leader: duty_leader,
          leader: { name: duty_leader.name, contact: duty_leader.phone || '' },
          staff: { name: duty_person.name, contact: duty_person.phone || '' },
          position: 'N/A',
          department: 'N/A',
          time: '全天'
        }
      },
      editable: false
    };
  });
};

/**
 * 将后端试验数据转换为 ScheduleEvent 格式
 * @param {Array} trials - 后端试验数据
 * @returns {Array<ScheduleEvent>} 转换后的 ScheduleEvent 数组
 */
export const transformTrialToEvents = (trials) => {
  return (Array.isArray(trials) ? trials : []).flatMap(trial =>
    (trial.time_slots || []).map(slot => {
      const start = fromServerFormat(slot.start_time);
      const end = fromServerFormat(slot.end_time);
      return {
        type: 'TRIAL',
        id: `slot_${slot.id}`,
        title: trial.title,
        start: start ? start.toDate() : null,
        end: end ? end.toDate() : null,
        extendedProps: {
          type: 'TRIAL',
          trialId: trial.id,
          description: trial.description, // 从 trial 获取 description
          equipment: trial.equipments,
          personnel: trial.responsible_persons,
          status: trial.status,
          client: trial.client,
          time_ranges: trial.time_slots.map(ts => ({ // 添加 time_ranges
            start_time: ts.start_time,
            end_time: ts.end_time,
          })),
        },
      };
    })
  );
};