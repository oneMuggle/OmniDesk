import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import RichTextEditor from '../../../shared/components/RichTextEditor';
import apiClient from '../../../shared/api/apiClient'; // 导入 apiClient
import './AnnouncementForm.css';

const AnnouncementForm = () => {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const editorRef = useRef(null);
  const { id } = useParams();
  const navigate = useNavigate();
  const isEditing = Boolean(id);

  // 恢复 PR-27 移除的图片上传能力:
  // file picker → POST /api/events/upload-image/ → editor.insertImage(url)
  const handleImageUpload = useCallback(() => {
    const input = document.createElement('input');
    input.setAttribute('type', 'file');
    input.setAttribute('accept', 'image/*');
    input.click();
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      const formData = new FormData();
      formData.append('image', file);
      try {
        const response = await apiClient.post('/api/events/upload-image/', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        const imageUrl = response.data.url;
        editorRef.current?.insertImage(imageUrl);
      } catch (err) {
        setError('图片上传失败: ' + (err.response?.data?.detail || err.message));
      }
    };
  }, []);

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
            ref={editorRef}
            value={content}
            onChange={(value) => setContent(value)}
            required
            style={{ height: '300px', marginBottom: '50px' }}
          />
        </div>
        <div className="form-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleImageUpload}
            disabled={loading}
          >
            插入图片
          </button>
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? '提交中...' : (isEditing ? '更新公告' : '发布公告')}
          </button>
        </div>
      </form>
    </div>
  );
};

export default AnnouncementForm;