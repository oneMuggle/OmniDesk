import React, { useEffect } from 'react';
import PropTypes from 'prop-types';
import { Modal, Form, Input, Button } from 'antd';

const BookForm = ({ book = null, onSave, onCancel }) => {
  const [form] = Form.useForm();

  useEffect(() => {
    if (book) {
      form.setFieldsValue({ title: book.title, author: book.author });
    } else {
      form.resetFields();
    }
  }, [book, form]);

  const handleSave = () => {
    form.validateFields()
      .then(values => {
        onSave({ ...book, ...values });
      })
      .catch(info => {
        console.log('Validate Failed:', info);
      });
  };

  return (
    <Modal
      title={book ? '编辑电子书' : '添加电子书'}
      open={!!book}
      onCancel={onCancel}
      footer={[
        <Button key="back" onClick={onCancel}>
          取消
        </Button>,
        <Button key="submit" type="primary" onClick={handleSave}>
          保存
        </Button>,
      ]}
    >
      <Form form={form} layout="vertical" name="book_form">
        <Form.Item
          name="title"
          label="书名"
          rules={[{ required: true, message: '请输入书名' }]}
        >
          <Input />
        </Form.Item>
        <Form.Item
          name="author"
          label="作者"
          rules={[{ required: true, message: '请输入作者' }]}
        >
          <Input />
        </Form.Item>
      </Form>
    </Modal>
  );
};

BookForm.propTypes = {
  book: PropTypes.shape({
    title: PropTypes.string,
    author: PropTypes.string,
  }),
  onSave: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
};


export default BookForm;