import React from 'react';
import PropTypes from 'prop-types';
import { Calendar, ConfigProvider } from 'antd';
import dayjs from 'dayjs';
import 'dayjs/locale/zh-cn'; // 引入 dayjs 的中文语言包
import locale from 'antd/es/locale/zh_CN'; // 引入 antd 的中文语言包
dayjs.locale('zh-cn'); // 设置 dayjs 语言为中文

const MiniCalendar = ({ memos, onSelectDate }) => {
  const cellRender = (value) => {
    const date = value.format('YYYY-MM-DD');
    const dayMemos = memos.filter(memo =>
      memo.reminder_time && dayjs(memo.reminder_time).format('YYYY-MM-DD') === date
    );

    return (
      <div className="date-cell-content">
        {dayMemos.length > 0 ? (
          <ul className="events" style={{ listStyle: 'none', margin: 0, padding: 0 }}>
            {dayMemos.map(memo => (
              <li key={memo.id}>
                <span className="memo-dot" style={{
                  display: 'inline-block',
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  backgroundColor: '#1890ff',
                  marginRight: '4px'
                }} />
              </li>
            ))}
          </ul>
        ) : (
          <span className="memo-placeholder" style={{ display: 'inline-block', width: '6px', height: '6px' }} />
        )}
      </div>
    );
  };

  return (
    <ConfigProvider locale={locale}>
      <Calendar
        fullscreen={false}
        onSelect={onSelectDate}
        cellRender={cellRender}
      />
    </ConfigProvider>
  );
};

MiniCalendar.propTypes = {
  memos: PropTypes.array.isRequired,
  onSelectDate: PropTypes.func.isRequired,
};

export default MiniCalendar;