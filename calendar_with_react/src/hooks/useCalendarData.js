import { useState, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { calendarApi } from '../api/calendar';
import { getTrials } from '../api/trials';
import { fromServerFormat } from '../utils/dateUtils';

export const useCalendarData = () => {
  const queryClient = useQueryClient();
  const [defaultEvents, setDefaultEvents] = useState([]);
  const [darkMode, setDarkMode] = useState(false);
  const [calendarType, setCalendarType] = useState('trial');
  const [currentEvent, setCurrentEvent] = useState(null);
  const [selectedTrial, setSelectedTrial] = useState(null);

  const { data: trials = [], isLoading: isTrialsLoading } = useQuery({
    queryKey: ['trials'],
    queryFn: () => getTrials().then(res => Array.isArray(res?.results) ? res.results : []),
    gcTime: 600000,
    staleTime: 300000
  });

  const { data: schedules = [], isLoading: isSchedulesLoading } = useQuery({
    queryKey: ['schedules'],
    queryFn: async () => {
      try {
        const response = await calendarApi.getSchedules();
        return Array.isArray(response) ? response : [];
      } catch (error) {
        console.error('获取排班数据失败:', error);
        return [];
      }
    },
    gcTime: 600000,
    staleTime: 300000
  });

  const { data: personnel = [], isLoading: isPersonnelLoading } = useQuery({
    queryKey: ['personnel'],
    queryFn: () => calendarApi.getPersonnel(),
    gcTime: 600000,
    staleTime: 300000
  });

  useEffect(() => {
    const fetchAllEvents = async (trials) => {
      if (!Array.isArray(trials) || trials.length === 0) return [];
      
      try {
        console.log('Fetching time slots for trials:', trials.map(t => t.id));
        const events = await Promise.all(
          trials.map(async (trial) => {
            try {
              const slots = await calendarApi.fetchTimeSlotsByTrial(trial.id);
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
    calendarType,
    setCalendarType,
    currentEvent,
    setCurrentEvent,
    selectedTrial,
    setSelectedTrial,
    queryClient
  };
};
