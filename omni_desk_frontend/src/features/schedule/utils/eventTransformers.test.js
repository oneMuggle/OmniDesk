import { transformScheduleToEvents, transformTrialToEvents } from './eventTransformers';

jest.mock('../../../shared/utils/dateUtils', () => ({
  fromServerFormat: (dateStr) => ({
    toDate: () => new Date(dateStr),
  }),
}));

describe('eventTransformers', () => {
  describe('transformScheduleToEvents', () => {
    it('should return empty array for non-array input', () => {
      expect(transformScheduleToEvents(null)).toEqual([]);
      expect(transformScheduleToEvents(undefined)).toEqual([]);
      expect(transformScheduleToEvents({})).toEqual([]);
    });

    it('should transform schedule data to events', () => {
      const schedules = [{
        id: 1,
        duty_date: '2024-01-15',
        duty_person: { id: 1, name: '张三', phone: '123' },
        duty_leader: { id: 2, name: '李四', phone: '456' },
      }];
      const events = transformScheduleToEvents(schedules);
      expect(events).toHaveLength(1);
      expect(events[0].type).toBe('SCHEDULE');
      expect(events[0].id).toBe('schedule-1');
      expect(events[0].title).toBe('张三');
      expect(events[0].allDay).toBe(true);
      expect(events[0].extendedProps.duty_person_name).toBe('张三');
      expect(events[0].extendedProps.duty_leader_name).toBe('李四');
    });

    it('should handle missing duty_person', () => {
      const schedules = [{ id: 1, duty_date: '2024-01-15' }];
      const events = transformScheduleToEvents(schedules);
      expect(events[0].title).toBe('未知');
    });
  });

  describe('transformTrialToEvents', () => {
    it('should return empty array for non-array input', () => {
      expect(transformTrialToEvents(null)).toEqual([]);
    });

    it('should transform trial data to events', () => {
      const trials = [{
        id: 1,
        title: 'Test Trial',
        description: 'Test description',
        status: 'active',
        client: 'Client A',
        equipments: [],
        responsible_persons: [],
        time_slots: [
          { id: 10, start_time: '2024-01-15T09:00:00', end_time: '2024-01-15T10:00:00' },
        ],
      }];
      const events = transformTrialToEvents(trials);
      expect(events).toHaveLength(1);
      expect(events[0].type).toBe('TRIAL');
      expect(events[0].title).toBe('Test Trial');
      expect(events[0].extendedProps.trialId).toBe(1);
      expect(events[0].extendedProps.time_ranges).toHaveLength(1);
    });

    it('should handle trial with no time_slots', () => {
      const trials = [{ id: 1, title: 'No Slots', time_slots: [] }];
      const events = transformTrialToEvents(trials);
      expect(events).toHaveLength(0);
    });
  });
});
