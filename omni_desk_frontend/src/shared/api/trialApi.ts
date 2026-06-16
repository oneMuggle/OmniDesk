import apiClient from './apiClient';
import { handleError } from './responseHandler';
import { toServerFormat } from '../utils/dateUtils';
import { logger } from '../utils/logger';

// 对应后端 omni_desk_backend/events/models.py Trial / serializers.py TrialSerializer
export type TrialStatus = 'planned' | 'in_progress' | 'completed' | 'cancelled';

export interface Trial {
    id: number;
    title: string;
    version: number;
    client: string;
    description: string;
    start_date: string | null;
    end_date: string | null;
    status: TrialStatus;
    created_at: string;
    updated_at: string;
    // 嵌套字段(read-only,后端填充)
    time_slots?: TimeSlot[];
    responsible_persons?: Array<{ id: number; name: string }>;
    equipments?: Array<{ id: number; name: string }>;
}

export interface TimeSlot {
    id?: number;
    trial?: number;
    start_time: string;
    end_time: string;
    description?: string;
}

// TODO: 后续 PR 完善类型 - 前端 Schedule 视图传入的 trial 数据形状
export interface TrialCreateInput {
    title: string;
    client: string;
    description?: string;
    start_date?: string | null;
    end_date?: string | null;
    status?: TrialStatus;
    equipmentIds?: number[];
    responsiblePersonIds?: number[];
    time_slots?: TimeSlot[];
    start?: string;
    end?: string;
}

export interface TrialUpdateInput {
    title?: string;
    client?: string;
    description?: string;
    start_date?: string | null;
    end_date?: string | null;
    status?: TrialStatus;
    equipmentIds?: number[];
    responsiblePersonIds?: number[];
    time_slots_data?: Array<Record<string, unknown>>;
}

export const trialApi = {
    fetchTrialEvents: async (): Promise<Trial[]> => {
        try {
            const response = await apiClient.get<{ results?: Trial[] } | Trial[]>('events/trials/');
            // 确保返回的是包含试验事件的数组
            if (Array.isArray(response.data)) {
                return response.data;
            }
            return response.data.results || [];
        } catch (error) {
            logger.error('Failed to fetch trial events:', error);
            handleError(error, false);
            throw error;
        }
    },

    createTrial: async (trialData: TrialCreateInput): Promise<Trial> => {
        try {
            const response = await apiClient.post<Trial>('events/trials/', {
                ...trialData,
                equipment_ids: trialData.equipmentIds || [],
                responsible_person_ids: trialData.responsiblePersonIds || [],
                time_periods: trialData.time_slots?.map((slot) => ({
                    start_time: toServerFormat(slot.start_time),
                    end_time: toServerFormat(slot.end_time),
                    description: slot.description || '',
                })) || [],
            }, {
                headers: {
                    'Content-Type': 'application/json',
                    'X-Request-Source': 'schedule-view',
                },
            });
            return response.data;
        } catch (error) {
            handleError({
                ...(error as object),
                name: (error as Error).name || 'ApiError',
                message: `创建试验失败: ${(error as Error).message}`,
                details: {
                    start: trialData.start,
                    end: trialData.end,
                },
            } as Error & { details: { start: string | undefined; end: string | undefined } }, false);
            throw new Error(`事件创建失败: ${(error as Error).message}`);
        }
    },

    updateTrial: async (trialId: number, trialData: TrialUpdateInput): Promise<Trial> => {
        try {
            const response = await apiClient.patch<Trial>(`events/trials/${trialId}/`, {
                ...trialData,
                equipment_ids: trialData.equipmentIds,
                responsible_person_ids: trialData.responsiblePersonIds,
                time_slots_data: trialData.time_slots_data || [],
            }, {
                headers: {
                    'Content-Type': 'application/json',
                    'X-Request-Source': 'schedule-view',
                },
            });
            return response.data;
        } catch (error) {
            handleError(error, false);
            throw error;
        }
    },

    fetchCalendarEvents: () => apiClient.get<Trial[]>('events/trials/'),
    updateCalendarEvent: (id: number, eventData: TrialUpdateInput) =>
        apiClient.put<Trial>(`events/trials/${id}/`, eventData as unknown as Trial),
    deleteCalendarEvent: (id: number) => apiClient.delete(`events/trials/${id}/`),

    deleteTrial: async (trialId: number): Promise<void> => {
        try {
            await apiClient.delete(`events/trials/${trialId}/`);
        } catch (error) {
            handleError(error, false);
            throw error;
        }
    },

    getTrialDetails: async (trialId: number): Promise<Trial> => {
        try {
            const response = await apiClient.get<Trial>(`events/trials/${trialId}/`);
            return response.data;
        } catch (error) {
            handleError(error, false);
            throw error;
        }
    },

    fetchTimeSlotsByTrial: async (trialId: number): Promise<TimeSlot[]> => {
        try {
            const response = await apiClient.get<{ results?: TimeSlot[] } | TimeSlot[]>(
                `events/time-slots/?trial=${trialId}`
            );
            if (Array.isArray(response.data)) {
                return response.data;
            }
            return response.data.results || [];
        } catch (error) {
            handleError(error, false);
            throw error;
        }
    },

    bulkCreateTimeSlots: async (trialId: number, timeSlots: TimeSlot[]): Promise<unknown> => {
        try {
            const response = await apiClient.post<unknown>('events/time-slots/bulk-create/', {
                trial: trialId,
                time_slots: timeSlots.map((slot) => ({
                    start_time: slot.start_time,
                    end_time: slot.end_time,
                    description: slot.description || '',
                })),
            });
            return response.data;
        } catch (error) {
            handleError(error, false);
            throw error;
        }
    },
};