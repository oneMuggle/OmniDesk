import React, { useState, useEffect } from 'react';
import Slider from 'react-slick';
import './AnnouncementsPage.css';

const AnnouncementsPage = () => {
  const [announcements, setAnnouncements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchAnnouncements = async () => {
      try {
        const response = await fetch('/api/announcements');
        if (!response.ok) throw new Error('获取公告失败');
        const data = await response.json();
        setAnnouncements(data);
      } catch (err) {
        setError(err.message);
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
    autoplaySpeed: 3000
  };

  return (
    <div className="announcements-container">
      <h2>系统公告</h2>
      {loading ? (
        <div className="loading-indicator">加载中...</div>
      ) : error ? (
        <div className="error-message">⚠️ {error}</div>
      ) : announcements.length > 0 ? (
        <Slider {...settings}>
          {announcements.map((item) => (
            <div key={item.id} className="announcement-slide">
              <div className="announcement-content">{item.content}</div>
            </div>
          ))}
        </Slider>
      ) : (
        <div className="no-announcements">暂无系统公告</div>
      )}
    </div>
  );
};

export default AnnouncementsPage;
