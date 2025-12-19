import { useQuery, useQueryClient } from '@tanstack/react-query';
import { trialApi } from '../../../api/trialApi';
import { transformTrialToEvents } from '../utils/eventTransformers';

export const useTrialScheduleData = () => {
  const queryClient = useQueryClient();

  const { data: trials = [], isLoading: isTrialsLoading } = useQuery({
    queryKey: ['trials'],
    queryFn: async () => {
      const data = await trialApi.fetchTrialEvents();
      return data;
    },
    gcTime: 600000,
    staleTime: 300000,
    refetchOnWindowFocus: false,
  });

  const trialEvents = transformTrialToEvents(trials);

  return {
    trials,
    isTrialsLoading,
    trialEvents,
    queryClient
  };
};
