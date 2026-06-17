import apiClient from './axiosConfig';

// 对应后端 omni_desk_backend/compliance/models.py ComplianceIssue
export type ComplianceIssueType =
    | '不规范'
    | '时间冲突'
    | '内容缺失'
    | '内容与规定不符'
    | '其他';

export type ComplianceIssueStatus = '待处理' | '处理中' | '已解决' | '已忽略';

export type ComplianceIssueSeverity = '低' | '中' | '高' | '紧急';

export interface ComplianceIssue {
    id: number;
    project: number;
    project_name: string;
    document_book: number | null;
    document_book_title: string;
    document_template: number | null;
    document_template_name: string;
    issue_type: ComplianceIssueType;
    description: string;
    location: string;
    status: ComplianceIssueStatus;
    severity: ComplianceIssueSeverity;
    due_date: string | null;
    created_at: string;
    updated_at: string;
}

export interface ComplianceIssueCreate {
    project: number;
    document_book?: number | null;
    document_template?: number | null;
    issue_type: ComplianceIssueType;
    description: string;
    location?: string;
    status?: ComplianceIssueStatus;
    severity?: ComplianceIssueSeverity;
    due_date?: string | null;
}

export interface ComplianceIssueUpdate extends Partial<ComplianceIssueCreate> {}

export type ComplianceIssueParams = Record<string, unknown>;

export function getAllComplianceIssues(params: ComplianceIssueParams = {}) {
    return apiClient.get<ComplianceIssue[]>('/api/compliance/', { params });
}

export function createComplianceIssue(data: ComplianceIssueCreate) {
    return apiClient.post<ComplianceIssue>('/api/compliance/', data);
}

export function updateComplianceIssue(id: number, data: ComplianceIssueUpdate) {
    return apiClient.put<ComplianceIssue>(`/api/compliance/${id}/`, data);
}

export function deleteComplianceIssue(id: number) {
    return apiClient.delete(`/api/compliance/${id}/`);
}

export function getComplianceIssue(id: number) {
    return apiClient.get<ComplianceIssue>(`/api/compliance/${id}/`);
}

export default {
    getAllComplianceIssues,
    createComplianceIssue,
    updateComplianceIssue,
    deleteComplianceIssue,
    getComplianceIssue,
};