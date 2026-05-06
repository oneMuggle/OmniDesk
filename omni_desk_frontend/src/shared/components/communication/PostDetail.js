import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Spin, List, Form, Input, Button, Avatar, Alert, Tag, Divider, Typography } from 'antd';
import {
  ArrowLeftOutlined,
  UserOutlined,
  ClockCircleOutlined,
  MessageOutlined,
  SendOutlined,
} from '@ant-design/icons';
import { getPost, createComment } from '../../../features/communication/api/communicationApi';
import './Communication.css';
import { sanitizeHtml } from '../../utils/sanitizeHtml';

const { TextArea } = Input;
const { Title, Paragraph } = Typography;

const PostDetail = () => {
    const { postId: urlPostId } = useParams();
    const navigate = useNavigate();
    const [post, setPost] = useState(null);
    const [comments, setComments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [submitting, setSubmitting] = useState(false);
    const [form] = Form.useForm();

    const fetchPost = useCallback(async () => {
        try {
            setLoading(true);
            const postResponse = await getPost(urlPostId);
            setPost(postResponse.data);
            if (Array.isArray(postResponse.data.comments)) {
                setComments(postResponse.data.comments);
            } else {
                setComments([]);
            }
        } catch (err) {
            setError('获取帖子失败，请稍后重试。');
            console.error('Failed to fetch post:', err);
        } finally {
            setLoading(false);
        }
    }, [urlPostId]);

    useEffect(() => {
        fetchPost();
    }, [fetchPost]);

    const handleSubmitComment = async (values) => {
        if (!values.comment) return;
        setSubmitting(true);
        try {
            await createComment(urlPostId, { content: values.comment });
            form.resetFields();
            await fetchPost();
        } catch (error) {
            console.error('Failed to submit comment:', error.response ? error.response.data : error);
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) {
        return (
            <div className="post-detail-loading">
                <Spin size="large" tip="加载中..." />
            </div>
        );
    }

    if (error) {
        return (
            <div className="post-detail-error">
                <Alert
                    message="错误"
                    description={error}
                    type="error"
                    showIcon
                    action={
                        <Button size="small" onClick={fetchPost}>
                            重试
                        </Button>
                    }
                />
            </div>
        );
    }

    if (!post) {
        return (
            <div className="post-detail-empty">
                <Alert
                    message="帖子不存在"
                    description="该帖子可能已被删除或您没有访问权限。"
                    type="info"
                    showIcon
                    action={
                        <Button size="small" onClick={() => navigate('/communication')}>
                            返回列表
                        </Button>
                    }
                />
            </div>
        );
    }

    const authorInitial = post.author ? post.author[0] : '?';

    return (
        <div className="post-detail-wrapper">
            {/* Back button & breadcrumb */}
            <div className="post-detail-breadcrumb">
                <Button
                    type="text"
                    icon={<ArrowLeftOutlined />}
                    onClick={() => navigate('/communication')}
                    className="back-btn"
                >
                    返回交流
                </Button>
            </div>

            {/* Main post card */}
            <Card className="post-detail-card" variant="borderless">
                <div className="post-detail-header">
                    <Title level={3} className="post-detail-title">
                        {post.title}
                    </Title>
                    <div className="post-detail-meta">
                        <Avatar size="large" style={{ backgroundColor: '#1677ff' }}>
                            {authorInitial}
                        </Avatar>
                        <div className="meta-info">
                            <div className="meta-author">
                                <UserOutlined /> {post.author || '未知用户'}
                            </div>
                            <div className="meta-date">
                                <ClockCircleOutlined />
                                {new Date(post.created_at).toLocaleString('zh-CN', {
                                    year: 'numeric',
                                    month: '2-digit',
                                    day: '2-digit',
                                    hour: '2-digit',
                                    minute: '2-digit',
                                })}
                            </div>
                        </div>
                        {post.tags && post.tags.length > 0 && (
                            <div className="post-tags">
                                {post.tags.map((tag) => (
                                    <Tag key={tag} color="blue">{tag}</Tag>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                <Divider className="post-divider" />

                <div
                    className="post-detail-content prose"
                    dangerouslySetInnerHTML={{ __html: sanitizeHtml(post.content) }}
                />
            </Card>

            {/* Comments section */}
            <Card className="comments-card" variant="borderless">
                <div className="comments-header">
                    <MessageOutlined className="comments-icon" />
                    <Title level={5} className="comments-title">
                        {comments.length} 条评论
                    </Title>
                </div>

                {comments.length > 0 ? (
                    <List
                        dataSource={comments}
                        renderItem={(item, index) => {
                            const itemAuthor = item.author || '匿名用户';
                            const itemInitial = itemAuthor[0];
                            return (
                                <List.Item className="comment-item" key={item.id || index}>
                                    <List.Item.Meta
                                        avatar={
                                            <Avatar
                                                style={{
                                                    backgroundColor: index % 2 === 0 ? '#722ed1' : '#13c2c2',
                                                }}
                                            >
                                                {itemInitial}
                                            </Avatar>
                                        }
                                        title={
                                            <span className="comment-author-name">
                                                {itemAuthor}
                                            </span>
                                        }
                                        description={
                                            <>
                                                <div className="comment-text">{item.content}</div>
                                                <div className="comment-date">
                                                    {new Date(item.created_at).toLocaleString('zh-CN', {
                                                        year: 'numeric',
                                                        month: '2-digit',
                                                        day: '2-digit',
                                                        hour: '2-digit',
                                                        minute: '2-digit',
                                                    })}
                                                </div>
                                            </>
                                        }
                                    />
                                </List.Item>
                            );
                        }}
                        itemLayout="horizontal"
                    />
                ) : (
                    <div className="no-comments">
                        <MessageOutlined style={{ fontSize: 32, color: '#bfbfbf', marginBottom: 8 }} />
                        <Paragraph type="secondary">暂无评论，快来抢沙发吧！</Paragraph>
                    </div>
                )}

                <Divider />

                <div className="comment-form-section">
                    <Title level={5}>发表评论</Title>
                    <Form form={form} onFinish={handleSubmitComment} layout="vertical">
                        <Form.Item
                            name="comment"
                            rules={[{ required: true, message: '请输入评论内容！' }]}
                        >
                            <TextArea
                                rows={4}
                                placeholder="写下你的想法..."
                                className="comment-textarea"
                            />
                        </Form.Item>
                        <Form.Item>
                            <Button
                                htmlType="submit"
                                loading={submitting}
                                type="primary"
                                icon={<SendOutlined />}
                                className="submit-comment-btn"
                            >
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