import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import apiClient from '../../../shared/api/apiClient'; // 导入 apiClient
import './ManageAnnouncementsPage.css';

const ManageAnnouncementsPage = () => {
  const [announcements, setAnnouncements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAnnouncements = async () => {
    try {
      const response = await apiClient.get('/api/events/announcements/');
      setAnnouncements(response.data.results); // 提取 results 字段
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
        await apiClient.delete(`/api/events/announcements/${id}/`);
        // 重新获取公告列表
        fetchAnnouncements();
      } catch (e) {
        setError(e.message);
      }
    }
  };

  if (loading) return <div className="loading-indicator">加载中...</div>;
  if (error) return <div className="error-message">⚠️ {error}</div>;

  return (
    <div className="manage-announcements-container">
      <h1>公告管理</h1>
      <Link to="/control-panel/announcements/new" className="btn btn-primary">
        发布新公告
      </Link>
      <table className="announcements-table">
        <thead>
          <tr>
            <th>标题</th>
            <th>发布者</th>
            <th>发布日期</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {announcements.map(announcement => (
            <tr key={announcement.id}>
              <td>{announcement.title}</td>
              <td>{announcement.author ? (announcement.author.real_name || announcement.author.username) : '匿名'}</td>
              <td>{new Date(announcement.created_at).toLocaleDateString()}</td>
              <td>
                <Link to={`/control-panel/announcements/edit/${announcement.id}`} className="btn btn-secondary">
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