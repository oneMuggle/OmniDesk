import { useQuery, useQueryClient } from '@tanstack/react-query';
import { trialApi } from '../api/trialApi';
import { fromServerFormat } from '../utils/dateUtils';

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

  const trialEvents = (Array.isArray(trials) ? trials : []).flatMap(trial =>
    (trial.time_slots || []).map(slot => {
      const start = fromServerFormat(slot.start_time);
      const end = fromServerFormat(slot.end_time);
      console.log(`Event ID: slot_${slot.id}, Start Type: ${typeof start}, Start Value: ${start}, End Type: ${typeof end}, End Value: ${end}`);
      return {
        ...slot,
        id: `slot_${slot.id}`,
        title: trial.title,
        start: start ? start.toDate() : null, // Convert dayjs object to Date object
        end: end ? end.toDate() : null,     // Convert dayjs object to Date object
        extendedProps: {
          type: 'TRIAL',
          trialId: trial.id,
          description: slot.description,
          equipment: trial.equipments,
          personnel: trial.responsible_persons,
          status: trial.status,
          client: trial.client,
        },
      };
    })
  );

  return {
    trials,
    isTrialsLoading,
    trialEvents,
    queryClient
  };
};
