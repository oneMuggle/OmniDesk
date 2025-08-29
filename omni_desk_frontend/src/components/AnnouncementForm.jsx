import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import ReactQuill from 'react-quill';
import 'react-quill/dist/quill.snow.css'; // 导入 Quill 的样式
import apiClient from '../api/apiClient'; // 导入 apiClient
import './AnnouncementForm.css';

const AnnouncementForm = () => {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const { id } = useParams();
  const navigate = useNavigate();
  const isEditing = Boolean(id);
  const quillRef = useRef(null);

  // 图片上传处理器
  const imageHandler = useCallback(() => {
    const input = document.createElement('input');
    input.setAttribute('type', 'file');
    input.setAttribute('accept', 'image/*');
    input.click();

    input.onchange = async () => {
      const file = input.files[0];
      if (file) {
        const formData = new FormData();
        formData.append('image', file);

        try {
          const response = await apiClient.post('/events/upload-image/', formData, {
            headers: {
              'Content-Type': 'multipart/form-data',
            },
          });
          const imageUrl = response.data.url;
          const quill = quillRef.current.getEditor();
          const range = quill.getSelection(true);
          quill.insertEmbed(range.index, 'image', imageUrl);
        } catch (err) {
          setError('图片上传失败: ' + (err.response?.data?.detail || err.message));
        }
      }
    };
  }, [setError, quillRef, apiClient]); // 添加依赖项

  const modules = useMemo(() => ({
    toolbar: {
      container: [
        [{ 'header': [1, 2, false] }],
        ['bold', 'italic', 'underline', 'strike', 'blockquote'],
        [{'list': 'ordered'}, {'list': 'bullet'}, {'indent': '-1'}, {'indent': '+1'}],
        ['link', 'image'],
        ['clean']
      ],
      handlers: {
        image: imageHandler,
      },
    },
  }), [imageHandler]); // 添加依赖项

  useEffect(() => {
    if (isEditing) {
      setLoading(true);
      apiClient.get(`/events/announcements/${id}/`)
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
        await apiClient.put(`/events/announcements/${id}/`, payload);
      } else {
        await apiClient.post('/events/announcements/', payload);
      }
      navigate('/admin/announcements');
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
          <ReactQuill
            ref={quillRef}
            theme="snow"
            value={content}
            onChange={(value) => setContent(value)}
            modules={modules}
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