import { useState, useEffect, useContext } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { RefreshContext } from '../../shared/context/RefreshContext';
import { List, Card, Button, Spin } from 'antd';
import { getPosts } from '../../features/communication/api/communicationApi';
import './Communication.css';

const PostList = () => {
    const [posts, setPosts] = useState([]);
    const [loading, setLoading] = useState(true);
    const { refreshKey } = useContext(RefreshContext);
    const navigate = useNavigate();

    useEffect(() => {
        const fetchPosts = async () => {
            setLoading(true);
            try {
                const response = await getPosts();
                setPosts([...(response.data.results || [])]);
            } catch (error) {
                console.error('Failed to fetch posts:', error);
                setPosts([]);
            } finally {
                setLoading(false);
            }
        };

        fetchPosts();
    }, [refreshKey]);

    if (loading) {
        return <Spin size="large" />;
    }

    return (
        <div className="post-list-container">
            <div className="post-list-header">
                <h1>帖子列表</h1>
                <Button type="primary">
                    <Link to="/communication/new">发布新帖</Link>
                </Button>
            </div>
            <List
                grid={{ gutter: 16, column: 1 }}
                dataSource={posts}
                renderItem={post => (
                    <List.Item>
                        <Card hoverable title={post.title} onClick={() => navigate(`/communication/${post.id}`)}>
                            <div className="post-content-summary">
                                {post.content.replace(/<[^>]*>?/gm, '').substring(0, 200)}...
                            </div>
                            <div className="post-meta">
                                <span><strong>作者:</strong> {post.author}</span>
                                <span><strong>发布于:</strong> {new Date(post.created_at).toLocaleString()}</span>
                            </div>
                        </Card>
                    </List.Item>
                )}
            />
        </div>
    );
};

export default PostList;