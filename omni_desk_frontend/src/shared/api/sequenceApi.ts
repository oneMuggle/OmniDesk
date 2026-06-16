import apiClient from './apiClient';

// 对应后端 omni_desk_backend/events/serializers.py PersonnelSequenceSerializer
export interface PersonnelSequence {
    id: number;
    name: string;
    sequence: number[];
    holiday_sequence: number[];
    personnel_details?: Array<{ id: number; name: string }>;
    holiday_personnel_details?: Array<{ id: number; name: string }>;
}

export interface PersonnelSequenceCreate {
    name: string;
    personnel?: number[];
    sequence?: number[];
    holiday_personnel?: number[];
    holiday_sequence?: number[];
}

export interface PersonnelSequenceUpdate extends Partial<PersonnelSequenceCreate> {}

// 对应后端 LeaderSequenceSerializer
export interface LeaderSequence {
    id: number;
    name: string;
    sequence: number[];
    personnel_details?: Array<{ id: number; name: string }>;
}

export interface LeaderSequenceCreate {
    name: string;
    personnel?: number[];
    sequence?: number[];
}

export interface LeaderSequenceUpdate extends Partial<LeaderSequenceCreate> {}

// ================== Personnel Sequence ==================

// 获取所有人员顺序
export const getPersonnelSequences = () => {
    return apiClient.get<PersonnelSequence[]>('events/personnel-sequences/');
};

// 获取单个人员顺序
export const getPersonnelSequenceDetails = (id: number) => {
    return apiClient.get<PersonnelSequence>(`events/personnel-sequences/${id}/`);
};

// 创建人员顺序
export const createPersonnelSequence = (data: PersonnelSequenceCreate) => {
    return apiClient.post<PersonnelSequence>('events/personnel-sequences/', data);
};

// 更新人员顺序
export const updatePersonnelSequence = (id: number, data: PersonnelSequenceUpdate) => {
    return apiClient.put<PersonnelSequence>(`events/personnel-sequences/${id}/`, data);
};

// 删除人员顺序
export const deletePersonnelSequence = (id: number) => {
    return apiClient.delete(`events/personnel-sequences/${id}/`);
};

// ================== Leader Sequence ==================

// 获取所有领导顺序
export const getLeaderSequences = () => {
    return apiClient.get<LeaderSequence[]>('events/leader-sequences/');
};

// 获取单个领导顺序
export const getLeaderSequenceDetails = (id: number) => {
    return apiClient.get<LeaderSequence>(`events/leader-sequences/${id}/`);
};

// 创建领导顺序
export const createLeaderSequence = (data: LeaderSequenceCreate) => {
    return apiClient.post<LeaderSequence>('events/leader-sequences/', data);
};

// 更新领导顺序
export const updateLeaderSequence = (id: number, data: LeaderSequenceUpdate) => {
    return apiClient.put<LeaderSequence>(`events/leader-sequences/${id}/`, data);
};

// 删除领导顺序
export const deleteLeaderSequence = (id: number) => {
    return apiClient.delete(`events/leader-sequences/${id}/`);
};