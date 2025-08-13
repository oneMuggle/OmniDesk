import React from 'react';
import { Calendar, ConfigProvider } from 'antd';
import moment from 'moment';
import 'moment/locale/zh-cn'; // 引入 moment 的中文语言包
import locale from 'antd/es/locale/zh_CN'; // 引入 antd 的中文语言包

moment.locale('zh-cn'); // 全局设置 moment 的语言为中文

const MiniCalendar = ({ memos, onSelectDate }) => {
  const dateCellRender = (value) => {
    const date = value.format('YYYY-MM-DD');
    const dayMemos = memos.filter(memo =>
      memo.reminder_time && moment(memo.reminder_time).format('YYYY-MM-DD') === date
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
        dateCellRender={dateCellRender}
      />
    </ConfigProvider>
  );
};

export default MiniCalendar;