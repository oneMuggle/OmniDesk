import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import Slider from 'react-slick';
import apiClient from '../../../shared/api/apiClient'; // 修正导入路径
import './AnnouncementsPage.css';
import { sanitizeHtml } from '../../../shared/utils/sanitizeHtml';

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

  const SampleNextArrow = (props) => {
    const { className, style, onClick } = props;
    return (
      <div
        className={className}
        style={{ ...style, display: "flex", alignItems: "center", justifyContent: "center", background: "transparent" }}
        onClick={onClick}
      >
        <svg fill="white" viewBox="0 0 24 24" width="40" height="40">
          <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z" />
        </svg>
      </div>
    );
  };

  SampleNextArrow.propTypes = {
    className: PropTypes.string,
    style: PropTypes.object,
    onClick: PropTypes.func,
  };

  const SamplePrevArrow = (props) => {
    const { className, style, onClick } = props;
    return (
      <div
        className={className}
        style={{ ...style, display: "flex", alignItems: "center", justifyContent: "center", background: "transparent" }}
        onClick={onClick}
      >
        <svg fill="white" viewBox="0 0 24 24" width="40" height="40">
          <path d="M15.41 16.59L10.83 12l4.58-4.59L14 6l-6 6 6 6 1.41-1.41z" />
        </svg>
      </div>
    );
  };

  SamplePrevArrow.propTypes = {
    className: PropTypes.string,
    style: PropTypes.object,
    onClick: PropTypes.func,
  };

  const settings = {
    dots: true,
    infinite: true,
    speed: 500,
    slidesToShow: 1,
    slidesToScroll: 1,
    autoplay: true,
    autoplaySpeed: 3000,
    centerMode: true,
    centerPadding: '60px',
    nextArrow: <SampleNextArrow />,
    prevArrow: <SamplePrevArrow />
  };

  return (
    <div className="announcements-container">
      <h2>系统公告</h2>
      {loading ? (
        <div className="loading-indicator">加载中...</div>
      ) : error ? (
        <div className="error-message">⚠️ {error}</div>
      ) : announcements?.length === 1 ? (
        <div className="announcement-single-container">
          <div key={announcements[0].id} className="announcement-slide">
            <h3 className="announcement-title">{announcements[0].title}</h3>
            <div className="announcement-content">
              <div
                className="announcement-html-content"
                dangerouslySetInnerHTML={{
                  __html: sanitizeHtml(expanded[announcements[0].id] || announcements[0].content.length <= 150
                    ? announcements[0].content
                    : `${announcements[0].content.replace(/<[^>]+>/g, '').substring(0, 100)}...`)
                }}
              />
              {announcements[0].content.replace(/<[^>]+>/g, '').length > 100 && (
                <button onClick={() => toggleExpand(announcements[0].id)} className="expand-btn">
                  {expanded[announcements[0].id] ? '收起' : '查看更多'}
                </button>
              )}
              <div className="announcement-meta">
                <span className="announcement-date">{new Date(announcements[0].created_at).toLocaleDateString()}</span>
                <span className="announcement-author">发布人：{announcements[0].author ? announcements[0].author.username : '匿名'}</span>
              </div>
            </div>
          </div>
        </div>
      ) : announcements?.length > 1 ? (
        <div className="slider-container">
          <Slider {...settings}>
            {announcements.map((item) => (
              <div key={item.id} className="announcement-slide">
                <h3 className="announcement-title">{item.title}</h3>
                <div className="announcement-content">
                  <div
                    className="announcement-html-content"
                    dangerouslySetInnerHTML={{
                      __html: sanitizeHtml(expanded[item.id] || item.content.length <= 150
                        ? item.content
                        : `${item.content.replace(/<[^>]+>/g, '').substring(0, 100)}...`)
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
        <div className="no-announcements">没有公告</div>
      )}
    </div>
  );
};

export default AnnouncementsPage;
