import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import RichTextEditor from '../../../shared/components/RichTextEditor';
import apiClient from '../../../shared/api/apiClient'; // 导入 apiClient
import './AnnouncementForm.css';

const AnnouncementForm = () => {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const { id } = useParams();
  const navigate = useNavigate();
  const isEditing = Boolean(id);

  // 注:原 quill 版本的 imageHandler / modules 工具栏已随 react-quill 一并移除。
  // tiptap StarterKit 默认不包含图片扩展;如需图片上传,请在 RichTextEditor 中引入
  // @tiptap/extension-image 并实现自定义 toolbar。

  useEffect(() => {
    if (isEditing) {
      setLoading(true);
      apiClient.get(`/api/events/announcements/${id}/`)
        .then(response => {
          setTitle(response.data.title);
          setContent(response.data.content);
        })
        .catch(e => setError(e.message))
        .finally(() => setLoading(false));
    }
  }, [id, isEditing]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const payload = { title, content };
    
    try {
      if (isEditing) {
        await apiClient.put(`/api/events/announcements/${id}/`, payload);
      } else {
        await apiClient.post('/api/events/announcements/', payload);
      }
      navigate('/control-panel/announcements');
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading && isEditing) return <div className="loading-indicator">加载中...</div>;

  return (
    <div className="announcement-form-container">
      <h1>{isEditing ? '编辑公告' : '发布新公告'}</h1>
      {error && <div className="error-message">⚠️ {error}</div>}
      <form onSubmit={handleSubmit} className="announcement-form">
        <div className="form-group">
          <label htmlFor="title">标题</label>
          <input
            type="text"
            id="title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="content">内容</label>
          <RichTextEditor
            value={content}
            onChange={(value) => setContent(value)}
            required
            style={{ height: '300px', marginBottom: '50px' }}
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? '提交中...' : (isEditing ? '更新公告' : '发布公告')}
        </button>
      </form>
    </div>
  );
};

export default AnnouncementForm;