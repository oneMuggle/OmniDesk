import { trialApi } from './trialApi';
import { timeSlotApi } from './timeSlotApi';
import { scheduleApi } from './scheduleApi';
import { personnelApi } from './personnelApi';
import { calendarEventApi } from './calendarEventApi';

export const calendarApi = {
  // 试验相关API - 使用trialApi模块
  fetchTrialEvents: trialApi.fetchTrialEvents,
  createTrial: trialApi.createTrial,
  updateTrial: trialApi.updateTrial,
  fetchCalendarEvents: trialApi.fetchCalendarEvents,
  updateCalendarEvent: trialApi.updateCalendarEvent,
  deleteCalendarEvent: trialApi.deleteCalendarEvent,

  // 时间段相关API - 使用timeSlotApi模块
  fetchTimeSlotsByTrial: timeSlotApi.fetchTimeSlotsByTrial,
  createTimeSlot: timeSlotApi.createTimeSlot,
  updateTimeSlot: timeSlotApi.updateTimeSlot,
  deleteTimeSlot: timeSlotApi.deleteTimeSlot,
  updateTimeSlotByIndex: timeSlotApi.updateTimeSlotByIndex,
  bulkUpdateTimeSlots: timeSlotApi.bulkUpdateTimeSlots,
  bulkCreateTimeSlots: timeSlotApi.bulkCreateTimeSlots,

  // 排班相关API - 使用scheduleApi模块
  getSchedules: scheduleApi.getSchedules,
  fetchSchedules: scheduleApi.fetchSchedules,
  createSchedule: scheduleApi.createSchedule,
  updateSchedule: scheduleApi.updateSchedule,
  deleteSchedule: scheduleApi.deleteSchedule,
  swapScheduleDates: scheduleApi.swapScheduleDates,

  // 人员相关API - 使用personnelApi模块
  getPersonnel: personnelApi.getPersonnel,

  // 创建通用日历事件 - 使用calendarEventApi模块
  createCalendarEvent: calendarEventApi.createCalendarEvent
};
