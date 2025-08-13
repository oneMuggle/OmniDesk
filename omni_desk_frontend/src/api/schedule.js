import { trialApi } from './trialApi';
import { timeSlotApi } from './timeSlotApi';
import * as personnelApi from './personnelApi';
import { scheduleEventApi } from './scheduleEventApi';

export const scheduleApi = {
  // 试验相关API - 使用trialApi模块
  // 试验相关API - 使用trialApi模块
  createTrialEvent: trialApi.createTrialEvent,
  updateTrialEvent: trialApi.updateTrialEvent,
  fetchTimeSlotsByTrial: timeSlotApi.fetchTimeSlotsByTrial,
  bulkCreateTimeSlots: timeSlotApi.bulkCreateTimeSlots,
  updateTimeSlot: timeSlotApi.updateTimeSlot,
  deleteTimeSlot: timeSlotApi.deleteTimeSlot,

  // 排班相关API - 使用scheduleApi模块
  getSchedules: scheduleApi.getSchedules,
  createOrUpdateSchedule: scheduleApi.createOrUpdateSchedule,
  deleteSchedule: scheduleApi.deleteSchedule,
  swapScheduleDates: scheduleApi.swapScheduleDates,
  updateScheduleDate: scheduleApi.updateScheduleDate,

  // 人员相关API - 使用personnelApi模块
  getPersonnel: personnelApi.getPersonnel,

  // 通用日程事件API
  createScheduleEvent: scheduleEventApi.createScheduleEvent,
};
