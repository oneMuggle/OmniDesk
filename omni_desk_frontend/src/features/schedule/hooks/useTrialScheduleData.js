import { useQuery, useQueryClient } from '@tanstack/react-query';
import { trialApi } from '../../../shared/api/trialApi';
import { transformTrialToEvents } from '../utils/eventTransformers';

export const useTrialScheduleData = () => {
  const queryClient = useQueryClient();

  const trialQuery = useQuery({
    queryKey: ['trials'],
    queryFn: trialApi.fetchTrialEvents,
    gcTime: 600000,
    staleTime: 300000,
    refetchOnWindowFocus: false,
  });

  const trials = trialQuery.data || [];
  const isTrialsLoading = trialQuery.isLoading;

  const trialEvents = transformTrialToEvents(trials);

  return {
    trials,
    isTrialsLoading,
    trialEvents,
    queryClient,
  };
};
