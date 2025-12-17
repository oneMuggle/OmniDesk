import React, { useEffect } from 'react';
import PropTypes from 'prop-types';
import { Modal, Form, Input, DatePicker, Switch, message } from 'antd';
import dayjs from 'dayjs';

const { TextArea } = Input;

const MemoModal = ({ open, onCancel, onSave, memoData = null, mode }) => {
  const [form] = Form.useForm();

  useEffect(() => {
    if (open && mode !== 'create') {
      form.setFieldsValue({
        ...memoData,
        reminder_time: memoData.reminder_time ? dayjs(memoData.reminder_time) : null,
      });
    } else if (open && mode === 'create') {
      form.resetFields();
    }
  }, [open, mode, memoData, form]);

  const handleOk = () => {
    form.validateFields()
      .then(values => {
        const payload = {
          ...values,
          reminder_time: values.reminder_time ? values.reminder_time.toISOString() : null,
        };
        onSave(payload, memoData?.id);
        form.resetFields();
      })
      .catch(info => {
        console.log('Validate Failed:', info);
        message.error('请填写所有必填项');
      });
  };

  return (
    <Modal
      open={open}
      title={mode === 'create' ? "新建备忘录" : "编辑备忘录"}
      okText={mode === 'create' ? "创建" : "保存"}
      cancelText="取消"
      onCancel={onCancel}
      onOk={handleOk}
    >
      <Form
        form={form}
        layout="vertical"
        name="memo_form"
      >
        <Form.Item
          name="title"
          label="标题"
          rules={[{ required: true, message: '请输入备忘录标题!' }]}
        >
          <Input />
        </Form.Item>
        <Form.Item
          name="content"
          label="内容"
        >
          <TextArea rows={4} />
        </Form.Item>
        <Form.Item
          name="reminder_time"
          label="提醒时间"
        >
          <DatePicker showTime format="YYYY-MM-DD HH:mm" />
        </Form.Item>
        <Form.Item
          name="is_completed"
          label="是否完成"
          valuePropName="checked"
        >
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  );
};

MemoModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onCancel: PropTypes.func.isRequired,
  onSave: PropTypes.func.isRequired,
  memoData: PropTypes.object,
  mode: PropTypes.string.isRequired,
};


export default MemoModal;