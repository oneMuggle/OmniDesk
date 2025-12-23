import apiClient from '../../../shared/api/apiClient';

export const getPosts = () => {
    return apiClient.get('/api/communication/posts/');
};

export const getPost = (id) => {
    return apiClient.get(`/api/communication/posts/${id}/`);
};

export const createPost = (data) => {
    return apiClient.post('/api/communication/posts/', data);
};

export const updatePost = (id, data) => {
    return apiClient.put(`/api/communication/posts/${id}/`, data);
};

export const deletePost = (id) => {
    return apiClient.delete(`/api/communication/posts/${id}/`);
};

export const createComment = (postId, commentData) => {
    return apiClient.post(`/api/communication/posts/${postId}/comments/`, commentData);
};