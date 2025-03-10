import React from 'react';
import Slider from 'react-slick';
import './AnnouncementsPage.css';

const AnnouncementsPage = () => {
  const announcements = [
    { id: 1, content: '系统维护通知：3月15日 2:00-4:00' },
    { id: 2, content: '新版功能说明会将于3月20日举行' },
    { id: 3, content: '用户隐私政策更新公告' }
  ];

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
      <Slider {...settings}>
        {announcements.map((item) => (
          <div key={item.id} className="announcement-slide">
            <div className="announcement-content">{item.content}</div>
          </div>
        ))}
      </Slider>
    </div>
  );
};

export default AnnouncementsPage;
