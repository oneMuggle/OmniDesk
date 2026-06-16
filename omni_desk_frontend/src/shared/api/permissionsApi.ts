import apiClient from './apiClient';

// 对应后端 omni_desk_backend/permissions/models.py PageRoute / Django Group
export interface PermissionGroup {
    id: number;
    name: string;
}

export interface PageRoute {
    id: number;
    name: string;
    path: string;
    component: string;
    parent: number | null;
    children?: PageRoute[];
}

export interface GroupPermissions {
    // TODO: 后续 PR 完善类型 - 当前用户权限响应可能因后端而异
    [key: string]: unknown;
}

export interface GroupPermissionsUpdate {
    permissions: number[];
}

export interface CreateGroupPayload {
    name: string;
}

export interface UpdateGroupPayload {
    name?: string;
}

// Helper to get CSRF token from cookies
const getCookie = (name: string): string | null => {
    let cookieValue: string | null = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === name + '=') {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
};

interface RequestOptions {
    method?: string;
    headers?: Record<string, string>;
    body?: string;
}

interface ApiErrorBody {
    detail?: string;
    message?: string;
}

// Helper to handle API requests
const request = async <T = unknown>(url: string, options: RequestOptions = {}): Promise<T> => {
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken') || '',
        ...(options.headers || {}),
    };

    const response = await fetch(`/api${url}`, { ...options, headers });

    if (!response.ok) {
        const error = (await response.json().catch(() => ({ message: response.statusText }))) as ApiErrorBody;
        throw new Error(error.detail || error.message || 'API request failed');
    }

    if (response.status === 204) {
        return null as T;
    }

    return (await response.json()) as T;
};

export const permissionsApi = {
    /**
     * Fetches all user groups.
     * GET /permissions/groups/
     */
    getGroups: () => apiClient.get<PermissionGroup[]>('/permissions/groups/'),

    /**
     * Creates a new user group.
     * POST /permissions/groups/
     */
    createGroup: (groupData: CreateGroupPayload) => {
        return request('/permissions/groups/', {
            method: 'POST',
            body: JSON.stringify(groupData),
        });
    },

    /**
     * Updates an existing user group.
     * PUT /permissions/groups/{id}/
     */
    updateGroup: (groupId: number, groupData: UpdateGroupPayload) => {
        return request(`/permissions/groups/${groupId}/`, {
            method: 'PUT',
            body: JSON.stringify(groupData),
        });
    },

    /**
     * Deletes a user group.
     * DELETE /permissions/groups/{id}/
     */
    deleteGroup: (groupId: number) => {
        return request(`/permissions/groups/${groupId}/`, {
            method: 'DELETE',
        });
    },

    /**
     * Fetches the entire page permission tree.
     * GET /permissions/pages/
     */
    getPageTree: () => {
        return request<PageRoute[]>('/permissions/pages/');
    },

    /**
     * Fetches permissions for a specific group.
     * GET /permissions/groups/{id}/permissions/
     */
    getGroupPermissions: (groupId: number) => {
        return request<GroupPermissions>(`/permissions/groups/${groupId}/permissions/`);
    },

    /**
     * Updates permissions for a specific group.
     * PUT /permissions/groups/{id}/permissions/
     */
    updateGroupPermissions: (groupId: number, permissionIds: number[]) => {
        return request(`/permissions/groups/${groupId}/permissions/`, {
            method: 'PUT',
            body: JSON.stringify({ permissions: permissionIds } satisfies GroupPermissionsUpdate),
        });
    },

    /**
     * Fetches permissions for the current user.
     * GET /permissions/users/me/permissions/
     */
    getMyPermissions: () => {
        return request<GroupPermissions>('/permissions/users/me/permissions/');
    },
};