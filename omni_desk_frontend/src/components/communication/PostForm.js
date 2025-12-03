import React, { useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { Form, Input, Button, DatePicker, Card, Space, message } from 'antd';
import ReactQuill from 'react-quill';
import 'react-quill/dist/quill.snow.css';
import * as communicationApi from '../../api/communicationApi';
import { RefreshContext } from '../../context/RefreshContext';

const PostForm = () => {
    const navigate = useNavigate();
    const [form] = Form.useForm();
    const { triggerRefresh } = useContext(RefreshContext);

    const onFinish = (values) => {
        const postData = {
            ...values,
            expiration_date: values.expiration_date ? values.expiration_date.format('YYYY-MM-DD HH:mm:ss') : null,
        };
        communicationApi.createPost(postData)
            .then(response => {
                message.success('帖子发布成功！');
                triggerRefresh();
                navigate('/communication');
            })
            .catch(error => {
                message.error('帖子发布失败，请重试。');
            });
    };

    const handleBack = () => {
        navigate('/communication');
    };

    const formItemLayout = {
        labelCol: {
            xs: { span: 24 },
            sm: { span: 4 },
        },
        wrapperCol: {
            xs: { span: 24 },
            sm: { span: 20 },
        },
    };

    const tailFormItemLayout = {
        wrapperCol: {
            xs: {
                span: 24,
                offset: 0,
            },
            sm: {
                span: 20,
                offset: 4,
            },
        },
    };

    return (
        <Card title="发布新帖" className="post-form-container">
            <Form
                {...formItemLayout}
                form={form}
                name="post"
                onFinish={onFinish}
                scrollToFirstError
            >
                <Form.Item
                    name="title"
                    label="标题"
                    rules={[
                        {
                            required: true,
                            message: '请输入标题!',
                        },
                    ]}
                >
                    <Input />
                </Form.Item>

                <Form.Item
                    name="content"
                    label="内容"
                    className="post-content-item"
                    rules={[
                        {
                            required: true,
                            message: '请输入内容!',
                        },
                    ]}
                >
                    <ReactQuill theme="snow" />
                </Form.Item>

                <Form.Item
                    name="expiration_date"
                    label="过期时间"
                >
                    <DatePicker showTime placeholder="选择日期和时间" format="YYYY-MM-DD HH:mm:ss" />
                </Form.Item>

                <Form.Item {...tailFormItemLayout}>
                    <Space>
                        <Button type="primary" htmlType="submit">
                            发布
                        </Button>
                        <Button onClick={handleBack}>
                            返回列表
                        </Button>
                    </Space>
                </Form.Item>
            </Form>
        </Card>
    );
};

export default PostForm;