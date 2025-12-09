import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Spin, List, Form, Input, Button, Avatar, Alert } from 'antd';
import { getPost } from '../../api/communicationApi';
import './Communication.css';

const { TextArea } = Input;

const PostDetail = () => {
    const { postId } = useParams();
    const [post, setPost] = useState(null);
    const [comments, setComments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [submitting, setSubmitting] = useState(false);
    const [form] = Form.useForm();

    useEffect(() => {
        const fetchPost = async () => {
            try {
                setLoading(true);
                const postResponse = await getPost(postId);
                setPost(postResponse.data);
                if (Array.isArray(postResponse.data.comments)) {
                    setComments(postResponse.data.comments);
                } else {
                    setComments([]);
                }
            } catch (err) {
                setError('Failed to fetch post. Please try again later.');
                console.error('Failed to fetch post:', err);
            } finally {
                setLoading(false);
            }
        };

        fetchPost();
    }, [postId]);

    const handleSubmitComment = async (values) => {
        if (!values.comment) return;
        setSubmitting(true);
        try {
            // Replace with your actual API call to create a comment
            // const response = await createComment({ post: id, content: values.comment });
            // setComments([...comments, response.data]);
            console.log('Submitting comment:', values.comment);
            form.resetFields();
        } catch (error) {
            console.error('Failed to submit comment:', error);
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) {
        return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}><Spin size="large" /></div>;
    }

    if (error) {
        return <Alert message="Error" description={error} type="error" showIcon />;
    }

    if (!post) {
        return <Alert message="Info" description="Post not found." type="info" showIcon />;
    }

    return (
        <div className="post-detail-container">
            <Card bordered={false}>
                <div className="post-header">
                    <h1 className="post-title">{post.title}</h1>
                    <div className="post-meta">
                        <span className="post-author"><strong>作者:</strong> {post.author || 'Unknown'}</span>
                        <span className="post-date"><strong>发布于:</strong> {new Date(post.created_at).toLocaleString()}</span>
                    </div>
                </div>
                <div className="post-content" dangerouslySetInnerHTML={{ __html: post.content }} />
            </Card>

            <Card className="comments-section" title={`${comments.length} 条评论`}>
                {comments.length > 0 ? (
                    <List
                        dataSource={comments}
                        itemLayout="horizontal"
                        renderItem={item => (
                            <List.Item className="comment-item">
                                <List.Item.Meta
                                    avatar={<Avatar>{item.author ? item.author[0] : 'U'}</Avatar>}
                                    title={<span className="comment-author">{item.author}</span>}
                                    description={<div className="comment-content">{item.content}</div>}
                                />
                                <div className="comment-date">{new Date(item.created_at).toLocaleString()}</div>
                            </List.Item>
                        )}
                    />
                ) : (
                    <div className="no-comments">暂无评论</div>
                )}
                <div className="comment-form">
                    <Form form={form} onFinish={handleSubmitComment} layout="vertical">
                        <Form.Item name="comment" label="你的评论" rules={[{ required: true, message: '请输入评论内容!' }]}>
                            <TextArea rows={4} placeholder="添加你的评论..." />
                        </Form.Item>
                        <Form.Item>
                            <Button htmlType="submit" loading={submitting} type="primary">
                                提交评论
                            </Button>
                        </Form.Item>
                    </Form>
                </div>
            </Card>
        </div>
    );
};

export default PostDetail;