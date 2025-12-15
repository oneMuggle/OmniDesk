import React from 'react';
import PropTypes from 'prop-types';
import { List, Card, Checkbox, Popconfirm } from 'antd';
import { EditOutlined, DeleteOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';

const MemoList = ({ memos, onEdit, onDelete, onToggleComplete, showActions = true, showReminderTime = true }) => {
  const sortedMemos = [...memos].sort((a, b) => {
    if (a.is_completed === b.is_completed) {
      return dayjs(a.reminder_time).valueOf() - dayjs(b.reminder_time).valueOf();
    }
    return a.is_completed ? 1 : -1;
  });

  return (
    <List
      grid={{ gutter: 16, column: 1 }}
      dataSource={sortedMemos}
      renderItem={memo => (
        <List.Item>
          <Card
            title={memo.title}
            actions={showActions ? [
              <Checkbox
                key="complete"
                checked={memo.is_completed}
                onChange={() => onToggleComplete(memo.id, !memo.is_completed)}
              >
                {memo.is_completed ? '已完成' : '未完成'}
              </Checkbox>,
              <EditOutlined key="edit" onClick={() => onEdit(memo)} />,
              <Popconfirm
                key="delete"
                title="确定删除此备忘录吗?"
                onConfirm={() => onDelete(memo.id)}
                okText="是"
                cancelText="否"
              >
                <DeleteOutlined />
              </Popconfirm>,
            ] : []}
          >
            <p>{memo.content}</p>
            {showReminderTime && memo.reminder_time && (
              <p>提醒时间: {dayjs(memo.reminder_time).format('YYYY-MM-DD HH:mm')}</p>
            )}
          </Card>
        </List.Item>
      )}
    />
  );
};

MemoList.propTypes = {
  memos: PropTypes.array.isRequired,
  onEdit: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
  onToggleComplete: PropTypes.func.isRequired,
  showActions: PropTypes.bool,
  showReminderTime: PropTypes.bool,
};

export default MemoList;