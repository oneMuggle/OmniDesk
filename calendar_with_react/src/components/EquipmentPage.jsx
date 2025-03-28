import React, { useState, useEffect } from 'react';
import { fetchEquipment, createEquipment, updateEquipment, deleteEquipment } from '../api/equipment';
import { Button, Table, Modal, Form, Input, message } from 'antd';

const EquipmentPage = () => {
    const [equipmentList, setEquipmentList] = useState([]);
    const [form] = Form.useForm();
    const [modalVisible, setModalVisible] = useState(false);
    const [editingEquipment, setEditingEquipment] = useState(null);

    useEffect(() => {
        loadEquipment();
    }, []);

    const loadEquipment = async () => {
        try {
            const data = await fetchEquipment();
            setEquipmentList(data);
        } catch (error) {
            message.error('获取设备数据失败');
        }
    };

    const handleSubmit = async (values) => {
        try {
            if (editingEquipment) {
                await updateEquipment(editingEquipment.id, values);
                message.success('设备更新成功');
            } else {
                await createEquipment(values);
                message.success('设备添加成功');
            }
            setModalVisible(false);
            loadEquipment();
        } catch (error) {
            message.error('操作失败');
        }
    };

    const handleDelete = async (id) => {
        try {
            await deleteEquipment(id);
            message.success('删除成功');
            loadEquipment();
        } catch (error) {
            message.error('删除失败');
        }
    };

    const columns = [
        {
            title: '设备名称',
            dataIndex: 'name',
            key: 'name',
        },
        {
            title: '设备简介',
            dataIndex: 'description',
            key: 'description',
        },
        {
            title: '操作',
            key: 'actions',
            render: (_, record) => (
                <>
                    <Button type="link" onClick={() => {
                        setEditingEquipment(record);
                        form.setFieldsValue(record);
                        setModalVisible(true);
                    }}>编辑</Button>
                    <Button type="link" danger onClick={() => handleDelete(record.id)}>删除</Button>
                </>
            ),
        },
    ];

    return (
        <div style={{ padding: 24 }}>
            <div style={{ marginBottom: 16 }}>
                <Button type="primary" onClick={() => {
                    setEditingEquipment(null);
                    form.resetFields();
                    setModalVisible(true);
                }}>添加设备</Button>
            </div>

            <Table 
                columns={columns} 
                dataSource={equipmentList} 
                rowKey="id"
                bordered
            />

            <Modal
                title={editingEquipment ? '编辑设备' : '新增设备'}
                visible={modalVisible}
                onCancel={() => setModalVisible(false)}
                onOk={() => form.submit()}
            >
                <Form form={form} onFinish={handleSubmit} layout="vertical">
                    <Form.Item
                        label="设备名称"
                        name="name"
                        rules={[{ required: true, message: '请输入设备名称' }]}
                    >
                        <Input />
                    </Form.Item>
                    <Form.Item
                        label="设备简介"
                        name="description"
                        rules={[{ required: true, message: '请输入设备简介' }]}
                    >
                        <Input.TextArea rows={4} />
                    </Form.Item>
                </Form>
            </Modal>
        </div>
    );
};

export default EquipmentPage;
