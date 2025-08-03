import React, { useState } from 'react';
import api from '../api/axiosConfig';
import './Commenting.css';

const Commenting = ({ chapterId, comments: initialComments }) => {
    const [comments, setComments] = useState(initialComments);
    const [newComment, setNewComment] = useState('');
    const [error, setError] = useState('');

    const handleCommentSubmit = async (e) => {
        e.preventDefault();
        if (!newComment.trim()) {
            setError('Comment cannot be empty.');
            return;
        }

        try {
            const response = await api.post(`/api/documents/chapters/${chapterId}/add_comment/`, {
                content: newComment,
            });
            setComments([...comments, response.data]);
            setNewComment('');
            setError('');
        } catch (err) {
            setError('Failed to post comment. Please try again.');
        }
    };

    return (
        <div className="commenting-section">
            <h3>评论</h3>
            <div className="comments-list">
                {comments.map(comment => (
                    <div key={comment.id} className="comment-item">
                        <p className="comment-user">{comment.user?.username || 'Anonymous'}</p>
                        <p className="comment-content">{comment.content}</p>
                        <p className="comment-date">{new Date(comment.created_at).toLocaleString()}</p>
                    </div>
                ))}
            </div>
            <form onSubmit={handleCommentSubmit} className="comment-form">
                <textarea
                    value={newComment}
                    onChange={(e) => setNewComment(e.target.value)}
                    placeholder="写下你的评论..."
                    rows="4"
                />
                <button type="submit">提交评论</button>
                {error && <p className="error-message">{error}</p>}
            </form>
        </div>
    );
};

export default Commenting;