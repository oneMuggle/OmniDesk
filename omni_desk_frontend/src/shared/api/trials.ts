import apiClient from './apiClient';
import { handleResponse, handleError } from './responseHandler';
import { logger } from '../utils/logger';

// 使用统一的 apiClient 实例
const api = apiClient;

// 试验状态选项(参照设备状态管理)
export const TRIAL_STATUS_OPTIONS = [
    { value: 'planned', label: '计划中' },
    { value: 'in_progress', label: '进行中' },
    { value: 'completed', label: '已完成' },
    { value: 'cancelled', label: '已取消' },
] as const;

export type TrialStatusValue = typeof TRIAL_STATUS_OPTIONS[number]['value'];

// TODO: 后续 PR 完善类型 - 试验查询参数
export type TrialListParams = Record<string, unknown>;

// TODO: 后续 PR 完善类型 - 试验创建/更新 DTO,与 TrialSerializer 对齐
export interface TrialPayload {
    title?: string;
    client?: string;
    description?: string;
    start_date?: string | null;
    end_date?: string | null;
    status?: TrialStatusValue;
    equipment_ids?: number[];
    responsible_person_ids?: number[];
    [key: string]: unknown;
}

// TODO: 后续 PR 完善类型 - 设备选项响应
export interface EquipmentOption {
    id: number;
    name: string;
    description?: string;
    serial_number?: string;
}

// TODO: 后续 PR 完善类型 - 人员选项响应
export interface PersonnelOption {
    id: number;
    name: string;
    department?: string;
    phone?: string;
}

interface PaginatedResponse<T> {
    results: T[];
    count: number;
}

// 试验管理 API(与后端 trials 端点保持一致)
// 获取试验列表(与后端接口保持一致)
export const getTrials = (params: TrialListParams = {}) => {
    return api.get('events/trials/', { params })
        .then(handleResponse)
        .catch(handleError);
};

// 保持原 fetchTrials 别名以兼容现有代码
export const fetchTrials = getTrials;

export const createTrial = (data: TrialPayload) => {
    return api.post('events/trials/', data)
        .then(handleResponse)
        .catch(handleError);
};

export const updateTrial = (id: number, data: TrialPayload) => {
    return api.patch(`events/trials/${id}/`, {
        ...data,
        equipment_ids: data.equipment_ids, // 保持字段名称一致性
    })
        .then(handleResponse)
        .catch(handleError);
};

export const deleteTrial = (id: number) => {
    return api.delete(`events/trials/${id}/`)
        .then(handleResponse)
        .catch(handleError);
};

export const getTrialById = async (id: number) => {
    try {
        const response = await api.get(`events/trials/${id}/`);
        return {
            data: handleResponse(response),
        };
    } catch (error) {
        logger.error('[MCP_ERROR] 获取试验详情失败:', error);
        throw handleError(error);
    }
};

// 获取关联资源(与设备/人员管理一致)
// 设备列表接口(保持命名一致性)
export const getEquipmentOptions = async (params: TrialListParams = {}) => {
    const response = await api.get('events/equipments/', { params })
        .catch((err: unknown) => {
            const axiosErr = err as { response?: { data?: unknown }; message?: string };
            logger.error('[MCP_ERROR] 设备选项请求失败:', axiosErr.response?.data || axiosErr.message);
            throw err;
        });
    const data = response.data as PaginatedResponse<{
        id: number;
        name: string;
        description?: string;
        serial_number?: string;
    }>;
    return {
        results: data.results.map((item) => ({
            id: item.id,
            name: item.name,
            description: item.description,
            serial_number: item.serial_number,
        })),
        count: data.count,
    };
};

export const getPersonnelOptions = async (params: TrialListParams = {}) => {
    const response = await api.get('personnel/personnel/', { params })
        .catch((err: unknown) => {
            const axiosErr = err as { response?: { data?: unknown }; message?: string };
            logger.error('[MCP_ERROR] 人员选项请求失败:', axiosErr.response?.data || axiosErr.message);
            throw err;
        });
    const data = response.data as PaginatedResponse<{
        id: number;
        name: string;
        department?: string;
        phone?: string;
    }>;
    return {
        results: data.results.map((person) => ({
            id: person.id,
            name: person.name,
            department: person.department,
            phone: person.phone,
        })),
        count: data.count,
    };
};