import React from 'react';
import { List, Card, Button, Checkbox, Popconfirm, message } from 'antd';
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
                checked={memo.is_completed}
                onChange={() => onToggleComplete(memo.id, !memo.is_completed)}
              >
                {memo.is_completed ? '已完成' : '未完成'}
              </Checkbox>,
              <EditOutlined key="edit" onClick={() => onEdit(memo)} />,
              <Popconfirm
                title="确定删除此备忘录吗?"
                onConfirm={() => onDelete(memo.id)}
                okText="是"
                cancelText="否"
              >
                <DeleteOutlined key="delete" />
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

export default MemoList;