import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Form, Input, Button, Upload, message } from 'antd';
import { UploadOutlined, PlusOutlined, MinusCircleOutlined } from '@ant-design/icons';
import apiClient from '../../../shared/api/apiClient';
import { notifications } from '../../../shared/utils/notifications';

const EditProfileForm = ({ userData = null, setUserData }) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [avatarFile, setAvatarFile] = useState(null);

  useEffect(() => {
    if (userData) {
      form.setFieldsValue({
        real_name: userData.real_name,
        email: userData.email,
        phone_numbers: userData.phone_numbers || [{ number: '' }],
      });
    }
  }, [userData, form]);

  const handleProfileUpdate = async (values) => {
    setLoading(true);
    const formData = new FormData();

    // Append text fields
    formData.append('real_name', values.real_name || '');
    formData.append('email', values.email || '');

    // Append phone numbers, filtering out empty ones
    if (values.phone_numbers) {
      const validPhoneNumbers = values.phone_numbers.filter(phone => phone && phone.number && phone.number.trim() !== '');
      validPhoneNumbers.forEach((phone, index) => {
        formData.append(`phone_numbers[${index}]number`, phone.number);
      });
    }
    
    // Append avatar if a new one was selected
    if (avatarFile) {
      formData.append('avatar', avatarFile);
    }

    try {
      const response = await apiClient.patch('users/me/profile/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setUserData(response.data);
      // Update form fields with new data, especially if phone numbers were changed server-side
      form.setFieldsValue({
        phone_numbers: response.data.phone_numbers || [{ number: '' }],
      });
      setAvatarFile(null); // Reset avatar file state
      notifications.showSuccess('个人资料更新成功！');
    } catch (error) {
      notifications.showError('个人资料更新失败。');
    } finally {
      setLoading(false);
    }
  };

  const onFinishFailed = (errorInfo) => {
    console.log('Failed:', errorInfo);
    message.error('请检查表单输入。');
  };

  const uploadProps = {
    name: 'avatar',
    beforeUpload: (file) => {
      const isJpgOrPng = file.type === 'image/jpeg' || file.type === 'image/png';
      if (!isJpgOrPng) {
        message.error('你只能上传 JPG/PNG 格式的图片!');
      }
      const isLt2M = file.size / 1024 / 1024 < 2;
      if (!isLt2M) {
        message.error('图片大小必须小于 2MB!');
      }
      if (isJpgOrPng && isLt2M) {
        setAvatarFile(file);
      }
      return false; // Prevent automatic upload
    },
    onRemove: () => {
        setAvatarFile(null);
    },
    fileList: avatarFile ? [avatarFile] : [],
  };

  if (!userData) {
    return <div>正在加载表单...</div>;
  }

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={handleProfileUpdate}
      onFinishFailed={onFinishFailed}
      initialValues={{
        real_name: userData.real_name,
        email: userData.email,
        phone_numbers: userData.phone_numbers && userData.phone_numbers.length > 0 ? userData.phone_numbers : [{ number: '' }],
      }}
    >
      <Form.Item
        label="真实姓名"
        name="real_name"
        rules={[{ required: true, message: '请输入您的真实姓名!' }]}
      >
        <Input />
      </Form.Item>

      <Form.Item
        label="电子邮箱"
        name="email"
        rules={[
          { required: true, message: '请输入您的电子邮箱!' },
          { type: 'email', message: '请输入有效的电子邮箱地址!' }
        ]}
      >
        <Input />
      </Form.Item>

      <Form.Item label="电话号码">
        <Form.List name="phone_numbers">
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name, ...restField }) => (
                <div key={key} style={{ display: 'flex', marginBottom: 8, gap: '8px' }}>
                  <Form.Item
                    {...restField}
                    name={[name, 'number']}
                    style={{ flex: 1, marginBottom: 0 }}
                    rules={[{ message: '请输入电话号码' }]}
                  >
                    <Input placeholder="输入电话号码" />
                  </Form.Item>
                  {fields.length > 1 ? (
                    <MinusCircleOutlined onClick={() => remove(name)} />
                  ) : null}
                </div>
              ))}
              <Form.Item>
                <Button
                  type="dashed"
                  onClick={() => add()}
                  block
                  icon={<PlusOutlined />}
                >
                  添加电话号码
                </Button>
              </Form.Item>
            </>
          )}
        </Form.List>
      </Form.Item>

      <Form.Item
        label="头像"
        name="avatar"
      >
        <Upload {...uploadProps}>
          <Button icon={<UploadOutlined />}>选择文件</Button>
        </Upload>
      </Form.Item>

      <Form.Item>
        <Button type="primary" htmlType="submit" loading={loading}>
          保存更改
        </Button>
      </Form.Item>
    </Form>
  );
};

EditProfileForm.propTypes = {
  userData: PropTypes.object,
  setUserData: PropTypes.func.isRequired,
};


export default EditProfileForm;