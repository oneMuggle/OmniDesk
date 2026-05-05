// Schedule Feature - Unified Exports
// Re-export all schedule-related modules for convenient imports

// API modules
export { scheduleApi } from './api/schedule';
export { scheduleApi as coreScheduleApi } from './api/scheduleApi';
export { scheduleApi as default } from './api/scheduleApi';
export { scheduleEventApi } from './api/scheduleEventApi';
export { holidayApi } from './api/holidayApi';
export { timeSlotApi } from './api/timeSlotApi';

// Page components
export { default as ScheduleManagementPage } from './pages/ScheduleManagementPage';
export { default as SchedulePage } from './pages/SchedulePage';
export { default as ScheduleSettingsPage } from './pages/ScheduleSettingsPage';
export { default as HolidayManagementPage } from './pages/HolidayManagementPage';

// Container/Complex components
export { default as TrialScheduleContainer } from './components/TrialScheduleContainer';
export { default as ShiftScheduleContainer } from './components/ShiftScheduleContainer';
export { default as CalendarContainer } from './components/CalendarContainer';

// Schedule sub-components
export { default as TrialSchedule } from './components/TrialSchedule';
export { default as ShiftSchedule } from './components/ShiftSchedule';
export { default as BaseSchedule } from './components/BaseSchedule';
export { default as ScheduleControls } from './components/ScheduleControls';
export { default as EventModal } from './components/EventModal';
export { default as CalendarEventModal } from './components/CalendarEventModal';
export { default as PersonnelScheduleModal } from './components/PersonnelScheduleModal';
export { default as TimeSlotForm } from './components/TimeSlotForm';
export { default as CustomTimeRangePicker } from './components/CustomTimeRangePicker';
export { default as ShiftCalendarPage } from './components/ShiftCalendarPage';
export { default as TrialCalendarPage } from './components/TrialCalendarPage';

// Calendar sub-components
export { default as ConfirmModal } from './components/Calendar/ConfirmModal';
export { default as EventModalContainer } from './components/Calendar/EventModal/EventModalContainer';

// Hooks
export { useScheduleData } from './hooks/useScheduleData';
export { useTrialScheduleData } from './hooks/useTrialScheduleData';
export { useCalendar } from './hooks/useCalendar';
export { useScheduleEventDrop } from './hooks/useScheduleEventDrop';

// Utils
export * from './utils/scheduleUtils';
export * from './utils/eventTransformers';
