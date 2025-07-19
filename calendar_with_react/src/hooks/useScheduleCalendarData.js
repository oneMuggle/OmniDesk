import { useQuery, useQueryClient } from '@tanstack/react-query';
import { scheduleApi } from '../api/scheduleApi';

export const useScheduleCalendarData = () => {
  const queryClient = useQueryClient();

  const { data: schedules = [], isLoading: isSchedulesLoading } = useQuery({
    queryKey: ['schedules'],
    queryFn: () => scheduleApi.getSchedules(),
    gcTime: 600000,
    staleTime: 300000
  });

  const { data: personnel = [], isLoading: isPersonnelLoading } = useQuery({
    queryKey: ['personnel'],
    queryFn: () => scheduleApi.getPersonnel(),
    gcTime: 600000,
    staleTime: 300000
  });


  return {
    schedules,
    isSchedulesLoading,
    personnel,
    isPersonnelLoading,
    queryClient
  };
};
