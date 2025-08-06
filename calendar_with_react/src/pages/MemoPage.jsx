import React, { useState, useEffect, useMemo } from 'react';
import { Layout, Row, Col, Button, Spin, Typography, Space, Card, message } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import moment from 'moment';
import { useMemoData } from '../hooks/useMemoData';
import MiniCalendar from '../components/Memo/MiniCalendar';
import MemoList from '../components/Memo/MemoList';
import MemoModal from '../components/Memo/MemoModal';
import '../components/Memo/memo.css';

const { Header, Content } = Layout;
const { Title } = Typography;

const MemoPage = () => {
  const { memos, isLoading, createMemo, updateMemo, deleteMemo } = useMemoData();
  const [selectedDate, setSelectedDate] = useState(moment());
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [currentMemo, setCurrentMemo] = useState(null);
  const [modalMode, setModalMode] = useState('create');

  // 使用 useMemo 优化派生状态的计算
  const memosForSelectedDate = useMemo(() => {
    return (memos || []).filter(memo =>
      memo.reminder_time && moment(memo.reminder_time).isSame(selectedDate, 'day')
    );
  }, [memos, selectedDate]);

  useEffect(() => {
    if (Notification.permission === 'granted') {
      (memos || []).forEach(memo => {
        if (memo.reminder_time && !memo.is_completed) {
          const reminderMoment = moment(memo.reminder_time);
          const now = moment();
          if (reminderMoment.isBetween(now.clone().subtract(1, 'minutes'), now.clone().add(5, 'minutes'))) {
            new Notification('备忘录提醒', {
              body: `${memo.title}\n${memo.content}`,
              icon: '/logo192.png'
            });
          }
        }
      });
    } else if (Notification.permission !== 'denied') {
      Notification.requestPermission();
    }
  }, [memos]);

  const handleSelectDate = (date) => {
    if (moment.isMoment(date)) {
      setSelectedDate(date);
    }
  };

  const handleAddMemo = () => {
    setCurrentMemo(null);
    setModalMode('create');
    setIsModalVisible(true);
  };

  const handleEditMemo = (memo) => {
    setCurrentMemo(memo);
    setModalMode('edit');
    setIsModalVisible(true);
  };

  const handleDeleteMemo = (id) => {
    deleteMemo(id, {
      onSuccess: () => message.success('备忘录已删除'),
      onError: () => message.error('删除失败，请重试'),
    });
  };

  const handleToggleComplete = (id, isCompleted) => {
    updateMemo({ id, data: { is_completed: isCompleted } }, {
      onSuccess: () => message.success(`备忘录已标记为${isCompleted ? '完成' : '未完成'}`),
      onError: () => message.error('状态更新失败，请重试'),
    });
  };

  const handleSaveMemo = (values, id) => {
    const action = modalMode === 'create' ? createMemo : (data) => updateMemo({ id, data });
    action(values, {
      onSuccess: () => {
        message.success(`备忘录已${modalMode === 'create' ? '创建' : '更新'}`);
        setIsModalVisible(false);
      },
      onError: () => message.error('保存失败，请重试'),
    });
  };

  if (isLoading) {
    return (
      <Layout style={{ minHeight: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        <Spin size="large" tip="加载备忘录中..." />
      </Layout>
    );
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#fff', padding: '0 24px', borderBottom: '1px solid #f0f0f0' }}>
        <Title level={3} style={{ margin: 0, lineHeight: '64px' }}>我的备忘录</Title>
      </Header>
      <Content style={{ padding: '24px' }}>
        <Row gutter={[24, 24]}>
          <Col xs={24} md={12}>
            <Card title="所有备忘录" extra={<Button type="primary" icon={<PlusOutlined />} onClick={handleAddMemo}>新建备忘录</Button>}>
              <MemoList
                memos={memos || []}
                onEdit={handleEditMemo}
                onDelete={handleDeleteMemo}
                onToggleComplete={handleToggleComplete}
              />
            </Card>
          </Col>

          <Col xs={24} md={12}>
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Card title="日历概览">
                <MiniCalendar memos={memos || []} onSelectDate={handleSelectDate} />
              </Card>

              <Card title={`选定日期备忘录 (${selectedDate.format('YYYY年MM月DD日')})`}>
                <MemoList
                  memos={memosForSelectedDate}
                  onEdit={handleEditMemo}
                  onDelete={handleDeleteMemo}
                  onToggleComplete={handleToggleComplete}
                />
              </Card>
            </Space>
          </Col>
        </Row>
      </Content>
      <MemoModal
        open={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        onSave={handleSaveMemo}
        memoData={currentMemo}
        mode={modalMode}
      />
    </Layout>
  );
};

export default MemoPage;