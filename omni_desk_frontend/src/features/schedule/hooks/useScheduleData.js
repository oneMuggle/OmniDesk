import { useState, useEffect, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { scheduleApi } from '../api/scheduleApi';
import { trialApi } from '../../../shared/api/trialApi';
import { logger } from '../../../shared/utils/logger';

export const useScheduleData = () => {
  const queryClient = useQueryClient();
  const [defaultEvents, setDefaultEvents] = useState([]);
  const [darkMode, setDarkMode] = useState(false);
  const [scheduleType, setScheduleType] = useState('trial');
  const [currentEvent, setCurrentEvent] = useState(null);
  const [selectedTrial, setSelectedTrial] = useState(null);

  // Shared trials query — uses same queryKey/queryFn as useTrialScheduleData
  // so React Query deduplicates the request across both hooks
  const trialsQuery = useQuery({
    queryKey: ['trials'],
    queryFn: trialApi.fetchTrialEvents,
    gcTime: 600000,
    staleTime: 300000,
    refetchOnWindowFocus: false,
  });
  const trials = useMemo(() => trialsQuery.data ?? [], [trialsQuery.data]);
  const isTrialsLoading = trialsQuery.isLoading;

  const schedulesQuery = useQuery({
    queryKey: ['schedules'],
    queryFn: async () => {
      try {
        const response = await scheduleApi.getSchedules();
        return Array.isArray(response) ? response : [];
      } catch (error) {
        logger.error('获取排班数据失败:', error);
        return [];
      }
    },
    gcTime: 600000,
    staleTime: 300000
  });
  const schedules = schedulesQuery.data ?? [];
  const isSchedulesLoading = schedulesQuery.isLoading;

  const personnelQuery = useQuery({
    queryKey: ['personnel'],
    queryFn: () => scheduleApi.getPersonnel().then(res => res.results || []),
    gcTime: 600000,
    staleTime: 300000
  });
  const personnel = personnelQuery.data ?? [];
  const isPersonnelLoading = personnelQuery.isLoading;

  useEffect(() => {
    const fetchAllEvents = async (trials) => {
      if (!Array.isArray(trials) || trials.length === 0) return [];
      
      try {
        const events = await Promise.all(
          trials.map(async (trial) => {
            try {
              const slots = await scheduleApi.fetchTimeSlotsByTrial(trial.id);
              return slots.map(slot => ({
                ...slot,
                trialId: trial.id,
                start: slot.start,
                end: slot.end
              }));
            } catch (error) {
              logger.error(`Error fetching slots for trial ${trial.id}:`, error);
              return [];
            }
          })
        );
        const flattened = events.flat();
        return flattened;
      } catch (error) {
        logger.error('Error loading time slots:', error);
        return [];
      }
    };

    if (trials && trials.length > 0) {
      fetchAllEvents(trials).then(events => {
        setDefaultEvents(events);
      });
    }
  }, [trials]);

  const toggleDarkMode = () => {
    setDarkMode(!darkMode);
  };

  return {
    trials,
    isTrialsLoading,
    schedules,
    isSchedulesLoading,
    personnel,
    isPersonnelLoading,
    defaultEvents,
    setDefaultEvents,
    darkMode,
    setDarkMode,
    toggleDarkMode,
    scheduleType,
    setScheduleType,
    currentEvent,
    setCurrentEvent,
    selectedTrial,
    setSelectedTrial,
    queryClient
  };
};
