import React, { useState, useEffect } from 'react';
import { Card, Table, Button, Modal, Form, Input, DatePicker, message, Popconfirm, Spin } from 'antd';
import moment from 'moment';
import { holidayApi } from '../api/holidayApi';

const HolidayManagementPage = () => {
  const [holidays, setHolidays] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [currentHoliday, setCurrentHoliday] = useState(null);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchHolidays();
  }, []);

  const fetchHolidays = async () => {
    setLoading(true);
    try {
      const data = await holidayApi.getHolidays();
      setHolidays(data);
    } catch (error) {
      message.error('获取节假日列表失败');
    } finally {
      setLoading(false);
    }
  };

  const showAddModal = () => {
    setCurrentHoliday(null);
    form.resetFields();
    setIsModalVisible(true);
  };

  const showEditModal = (holiday) => {
    setCurrentHoliday(holiday);
    form.setFieldsValue({
      name: holiday.name,
      dateRange: [moment(holiday.start_date), moment(holiday.end_date)],
    });
    setIsModalVisible(true);
  };

  const handleCancel = () => {
    setIsModalVisible(false);
    setCurrentHoliday(null);
    form.resetFields();
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      const [startDate, endDate] = values.dateRange;
      const holidayData = {
        name: values.name,
        start_date: startDate.format('YYYY-MM-DD'),
        end_date: endDate.format('YYYY-MM-DD'),
      };

      if (currentHoliday) {
        await holidayApi.updateHoliday(currentHoliday.id, holidayData);
        message.success('节假日更新成功');
      } else {
        await holidayApi.createHoliday(holidayData);
        message.success('节假日添加成功');
      }
      fetchHolidays();
      handleCancel();
    } catch (error) {
      message.error(currentHoliday ? '更新节假日失败' : '添加节假日失败');
    }
  };

  const handleDelete = async (id) => {
    try {
      await holidayApi.deleteHoliday(id);
      message.success('节假日删除成功');
      fetchHolidays();
    } catch (error) {
      message.error('删除节假日失败');
    }
  };

  const columns = [
    {
      title: '节假日名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '开始日期',
      dataIndex: 'start_date',
      key: 'start_date',
    },
    {
      title: '结束日期',
      dataIndex: 'end_date',
      key: 'end_date',
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <>
          <Button type="link" onClick={() => showEditModal(record)}>编辑</Button>
          <Popconfirm
            title="确定要删除这个节假日吗?"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" danger>删除</Button>
          </Popconfirm>
        </>
      ),
    },
  ];

  return (
    <Card>
      <Button type="primary" onClick={showAddModal} style={{ marginBottom: 16 }}>
        添加节假日
      </Button>
      <Spin spinning={loading}>
        <Table
          columns={columns}
          dataSource={holidays}
          rowKey="id"
          bordered
        />
      </Spin>
      <Modal
        title={currentHoliday ? "编辑节假日" : "添加节假日"}
        open={isModalVisible}
        onOk={handleOk}
        onCancel={handleCancel}
        okText={currentHoliday ? "更新" : "添加"}
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="节假日名称"
            rules={[{ required: true, message: '请输入节假日名称!' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="dateRange"
            label="日期范围"
            rules={[{ required: true, message: '请选择日期范围!' }]}
          >
            <DatePicker.RangePicker style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
};

export default HolidayManagementPage;