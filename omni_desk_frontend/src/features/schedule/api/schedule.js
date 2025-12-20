import { trialApi } from '../../../shared/api/trialApi';
import { timeSlotApi } from './timeSlotApi';
import * as personnelApi from '../../personnel/api/personnelApi';
import { scheduleEventApi } from './scheduleEventApi';
import { scheduleApi as coreScheduleApi } from './scheduleApi'; // 导入原始的 scheduleApi 并重命名

export const scheduleApi = {
  // 试验相关API - 使用trialApi模块
  createTrialEvent: trialApi.createTrialEvent,
  updateTrialEvent: trialApi.updateTrialEvent,
  fetchTimeSlotsByTrial: timeSlotApi.fetchTimeSlotsByTrial,
  bulkCreateTimeSlots: timeSlotApi.bulkCreateTimeSlots,
  updateTimeSlot: timeSlotApi.updateTimeSlot,
  deleteTimeSlot: timeSlotApi.deleteTimeSlot,

  // 排班相关API - 使用coreScheduleApi模块
  getSchedules: coreScheduleApi.getSchedules,
  createOrUpdateSchedule: coreScheduleApi.createOrUpdateSchedule,
  deleteSchedule: coreScheduleApi.deleteSchedule,
  swapScheduleDates: coreScheduleApi.swapScheduleDates,
  updateScheduleDate: coreScheduleApi.updateScheduleDate,

  // 人员相关API - 使用personnelApi模块
  getPersonnel: personnelApi.getPersonnel,

  // 通用日程事件API
  createScheduleEvent: scheduleEventApi.createScheduleEvent,
};
