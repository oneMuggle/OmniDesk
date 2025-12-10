import apiClient from './apiClient';

export const getPosts = () => {
    return apiClient.get('/communication/posts/');
};

export const getPost = (id) => {
    return apiClient.get(`/communication/posts/${id}/`);
};

export const createPost = (data) => {
    return apiClient.post('/communication/posts/', data);
};

export const updatePost = (id, data) => {
    return apiClient.put(`/communication/posts/${id}/`, data);
};

export const deletePost = (id) => {
    return apiClient.delete(`/communication/posts/${id}/`);
};

export const createComment = (postId, commentData) => {
    return apiClient.post(`/communication/posts/${postId}/comments/`, commentData);
};