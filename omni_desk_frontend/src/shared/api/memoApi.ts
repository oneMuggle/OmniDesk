import apiClient from './apiClient';

// 对应后端 omni_desk_backend/memos/models.py Memo
export interface Memo {
    id: number;
    title: string;
    content: string;
    reminder_time: string | null;
    is_completed: boolean;
    user: number;
    created_at: string;
    updated_at: string;
}

export interface MemoCreate {
    title: string;
    content?: string;
    reminder_time?: string | null;
    is_completed?: boolean;
}

export interface MemoUpdate extends Partial<MemoCreate> {}

const memoApi = {
    getAllMemos: () => {
        return apiClient.get<Memo[]>('memos/');
    },
    createMemo: (data: MemoCreate) => {
        return apiClient.post<Memo>('memos/', data);
    },
    patchMemo: (id: number, data: MemoUpdate) => {
        return apiClient.patch<Memo>(`memos/${id}/`, data);
    },
    deleteMemo: (id: number) => {
        return apiClient.delete(`memos/${id}/`);
    },
};

export default memoApi;