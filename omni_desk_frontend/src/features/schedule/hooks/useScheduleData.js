import { useState, useEffect, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { scheduleEventApi as scheduleApi } from '../api/scheduleEventApi';
import { getTrials } from '../../../shared/api/trials';

export const useScheduleData = () => {
  const queryClient = useQueryClient();
  const [defaultEvents, setDefaultEvents] = useState([]);
  const [darkMode, setDarkMode] = useState(false);
  const [scheduleType, setScheduleType] = useState('trial');
  const [currentEvent, setCurrentEvent] = useState(null);
  const [selectedTrial, setSelectedTrial] = useState(null);

  const trialsQuery = useQuery({
    queryKey: ['trials'],
    queryFn: () => getTrials().then(res => Array.isArray(res?.results) ? res.results : []),
    gcTime: 600000,
    staleTime: 300000
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
        console.error('获取排班数据失败:', error);
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
        console.log('Fetching time slots for trials:', trials.map(t => t.id));
        const events = await Promise.all(
          trials.map(async (trial) => {
            try {
              const slots = await scheduleApi.fetchTimeSlotsByTrial(trial.id);
              console.log(`Fetched ${slots.length} slots for trial ${trial.id}`);
              return slots.map(slot => ({
                ...slot,
                trialId: trial.id,
                start: slot.start,
                end: slot.end
              }));
            } catch (error) {
              console.error(`Error fetching slots for trial ${trial.id}:`, error);
              return [];
            }
          })
        );
        const flattened = events.flat();
        console.log('Total time slots loaded:', flattened.length);
        return flattened;
      } catch (error) {
        console.error('Error loading time slots:', error);
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
