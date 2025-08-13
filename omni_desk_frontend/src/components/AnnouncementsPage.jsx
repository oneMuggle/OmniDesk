import React, { useState, useEffect } from 'react';
import Slider from 'react-slick';
import apiClient from '../api/apiClient'; // 修正导入路径
import './AnnouncementsPage.css';

const AnnouncementsPage = () => {
  const [announcements, setAnnouncements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState({});

  const toggleExpand = (id) => {
    setExpanded(prev => ({ ...prev, [id]: !prev[id] }));
  };

  useEffect(() => {
    const fetchAnnouncements = async () => {
      try {
        // 使用 apiClient 发起请求
        const response = await apiClient.get('/events/announcements/');
        setAnnouncements(response.data.results); // 提取 results 字段
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };

    fetchAnnouncements();
  }, []);

  const settings = {
    dots: true,
    infinite: true,
    speed: 500,
    slidesToShow: 1,
    slidesToScroll: 1,
    autoplay: true,
    autoplaySpeed: 3000,
    centerMode: true,
    centerPadding: '60px'
  };

  return (
    <div className="announcements-container">
      <h2>系统公告</h2>
      {loading ? (
        <div className="loading-indicator">加载中...</div>
      ) : error ? (
        <div className="error-message">⚠️ {error}</div>
      ) : announcements.length > 0 ? (
        <div className="slider-container">
          <Slider {...settings}>
            {announcements.map((item) => (
              <div key={item.id} className="announcement-slide">
                <h3 className="announcement-title">{item.title}</h3>
                <div className="announcement-content">
                  <div
                    className="announcement-html-content"
                    dangerouslySetInnerHTML={{
                      __html: expanded[item.id] || item.content.length <= 150
                        ? item.content
                        : `${item.content.replace(/<[^>]+>/g, '').substring(0, 100)}...`
                    }}
                  />
                  {item.content.replace(/<[^>]+>/g, '').length > 100 && (
                    <button onClick={() => toggleExpand(item.id)} className="expand-btn">
                      {expanded[item.id] ? '收起' : '查看更多'}
                    </button>
                  )}
                  <div className="announcement-meta">
                    <span className="announcement-date">{new Date(item.created_at).toLocaleDateString()}</span>
                    <span className="announcement-author">发布人：{item.author ? item.author.username : '匿名'}</span>
                  </div>
                </div>
              </div>
            ))}
          </Slider>
        </div>
      ) : (
        <div className="no-announcements">暂无系统公告</div>
      )}
    </div>
  );
};

export default AnnouncementsPage;
