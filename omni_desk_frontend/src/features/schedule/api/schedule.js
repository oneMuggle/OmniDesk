import { timeSlotApi } from './timeSlotApi';
import * as personnelApi from '../../personnel/api/personnelApi';
import { scheduleApi as coreScheduleApi } from './scheduleApi';

export const scheduleApi = {
  // 试验相关API - 使用timeSlotApi模块
  fetchTimeSlotsByTrial: timeSlotApi.fetchTimeSlotsByTrial,
  bulkCreateTimeSlots: timeSlotApi.bulkCreateTimeSlots,
  updateTimeSlot: timeSlotApi.updateTimeSlot,
  deleteTimeSlot: timeSlotApi.deleteTimeSlot,

  // 排班相关API - 使用coreScheduleApi模块
  getSchedules: coreScheduleApi.getSchedules,
  createSchedule: coreScheduleApi.createSchedule,
  updateSchedule: coreScheduleApi.updateSchedule,
  deleteSchedule: coreScheduleApi.deleteSchedule,
  swapScheduleDates: coreScheduleApi.swapScheduleDates,
  updateScheduleDate: coreScheduleApi.updateScheduleDate,

  // 人员相关API - 使用personnelApi模块
  getPersonnel: personnelApi.getPersonnel,

  // 设备相关API - 使用coreScheduleApi模块
  fetchEquipment: coreScheduleApi.fetchEquipment,
};
