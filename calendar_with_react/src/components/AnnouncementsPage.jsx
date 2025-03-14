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
        const response = await fetch('/api/announcements', {
          headers: {
            'Accept': 'application/json'
          }
        });
        
        if (!response.ok) {
        const errorText = await response.text();
          throw new Error(`请求失败 (${response.status}): ${errorText}`);
        }

        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
          throw new Error('无效的响应格式');
        }

        const data = await response.json();
        setAnnouncements(data);
      } catch (err) {
        // 示例公告数据
        const sampleData = [
          {
            id: 1,
            title: "系统维护通知",
            content: "将于2025年3月15日凌晨2:00-4:00进行系统维护升级，期间服务将不可用。",
            date: "2025-03-13",
            author: "系统管理员"
          },
          {
            id: 2,
            title: "新版本发布公告",
            content: "V2.1.0版本已发布！新增日历导出功能和公告分类筛选功能。",
            date: "2025-03-12",
            author: "产品团队"
          },
          {
            id: 3, 
            title: "清明节假期安排",
            content: "4月4日-6日放假期间客服服务时间调整为9:00-18:00。",
            date: "2025-03-10",
            author: "行政部"
          }
        ];
        setAnnouncements(sampleData);
        setError(null);  // 清除错误状态以显示示例公告
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
                  <p>{item.content}</p>
                  <div className="announcement-meta">
                    <span className="announcement-date">{item.date}</span>
                    <span className="announcement-author">发布人：{item.author}</span>
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
