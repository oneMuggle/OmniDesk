import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { message } from 'antd';
import apiClient from '../../../shared/api/apiClient'; // 导入 apiClient
import './ManageAnnouncementsPage.css';
import { extractResults } from '../../../shared/api/responseHandler';

const ManageAnnouncementsPage = () => {
  const [announcements, setAnnouncements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAnnouncements = async () => {
    try {
      // 管理页包含草稿（仅管理员 / HR 生效）；公告页不带此参数，只显示已发布
      const response = await apiClient.get('events/announcements/', { params: { include_drafts: 1 } });
      setAnnouncements(extractResults(response.data)); // 提取 results 字段
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnnouncements();
  }, []);

  const handleDelete = async (id) => {
    if (window.confirm('你确定要删除这条公告吗？')) {
      try {
        await apiClient.delete(`events/announcements/${id}/`);
        // 重新获取公告列表
        fetchAnnouncements();
      } catch (e) {
        setError(e.message);
      }
    }
  };

  const handlePublish = async (announcement) => {
    if (!window.confirm(`发布后会通知全体用户，确定发布「${announcement.title}」吗？`)) return;
    try {
      await apiClient.post(`events/announcements/${announcement.id}/publish/`);
      message.success('公告已发布');
    } catch (e) {
      message.error(e.response?.status === 409 ? '该公告已发布' : (e.response?.data?.detail || '发布失败，请稍后重试'));
    }
    fetchAnnouncements();
  };

  if (loading) return <div className="loading-indicator">加载中...</div>;
  if (error) return <div className="error-message">⚠️ {error}</div>;

  return (
    <div className="manage-announcements-container">
      <h1>公告管理</h1>
      <Link to="/control-panel/announcements/create" className="btn btn-primary">
        发布新公告
      </Link>
      <table className="announcements-table">
        <thead>
          <tr>
            <th>标题</th>
            <th>状态</th>
            <th>发布者</th>
            <th>发布日期</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {announcements.map(announcement => (
            <tr key={announcement.id}>
              <td>{announcement.title}</td>
              <td>
                {announcement.status === 'draft'
                  ? <span className="status-badge status-draft">草稿</span>
                  : <span className="status-badge status-published">已发布</span>}
              </td>
              <td>{announcement.author ? (announcement.author.real_name || announcement.author.username) : '匿名'}</td>
              <td>
                {announcement.status === 'draft'
                  ? '—'
                  : new Date(announcement.published_at || announcement.created_at).toLocaleDateString()}
              </td>
              <td>
                {announcement.status === 'draft' && (
                  <button onClick={() => handlePublish(announcement)} className="btn btn-success">
                    发布
                  </button>
                )}
                <Link to={`/control-panel/announcements/${announcement.id}/edit`} className="btn btn-secondary">
                  编辑
                </Link>
                <button onClick={() => handleDelete(announcement.id)} className="btn btn-danger">
                  删除
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default ManageAnnouncementsPage;