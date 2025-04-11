import React, { useState, useEffect } from 'react';
import { Button, Form, Select, DatePicker, Badge, Space, Input } from 'antd';
import { useQueryClient } from '@tanstack/react-query';
import Modal from 'antd/es/modal';
import ConfirmModal from '../ConfirmModal';
import { calendarApi } from '../../../api/calendar';
import { getTrials } from '../../../api/trials';
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';
import TrialDetails from './TrialDetails';
import { fromServerFormat, toServerFormat } from '../../../utils/dateUtils';
import moment from 'moment';

const EventModal = ({
  currentEvent,
  modalType,
  form,
  trials,
  isTrialsLoading,
  selectedTrial,
  isEditing,
  modifiedSlots,
  handleEventSubmit,
  setCurrentEvent,
  setIsEditing,
  setModifiedSlots,
  setDefaultEvents = () => console.warn('setDefaultEvents not implemented'),
  setSelectedTrial
}) => {
  const queryClient = useQueryClient();
  const [autoSaveStatus, setAutoSaveStatus] = useState(null); // null, 'saving', 'saved', 'error'
  const [autoSaveTimer, setAutoSaveTimer] = useState(null);

  // 自动设置关联试验
  useEffect(() => {
    if (currentEvent?.trialId) {
      const trial = trials.find(t => t.id === currentEvent.trialId);
      if (trial) {
        form.setFieldsValue({ trial: trial.id });
        setSelectedTrial(trial);
      }
    }
  }, [currentEvent, trials]);

  // 自动保存逻辑
  useEffect(() => {
    return () => {
      if (autoSaveTimer) {
        clearTimeout(autoSaveTimer);
      }
    };
  }, [autoSaveTimer]);

  const handleAutoSave = async () => {
    if (!isEditing) return;
    
    setAutoSaveStatus('saving');
    try {
      // 复用现有的保存逻辑
      await handleManualSave();
      setAutoSaveStatus('saved');
      setTimeout(() => setAutoSaveStatus(null), 2000);
    } catch (error) {
      setAutoSaveStatus('error');
      console.error('自动保存失败:', error);
    }
  };

  const handleManualSave = async () => {
    // 检查试验项目是否已选择
    const trialId = form.getFieldValue('trial');
    if (!trialId) {
      Modal.error({
        title: '验证失败',
        content: '请先选择试验项目',
      });
      return;
    }

    // 增强的时间段验证逻辑
    const formValues = form.getFieldsValue(true);
    console.log('原始表单数据:', formValues);

    // 验证time_slots数据结构
    const timeSlots = formValues.time_slots || [];
    if (!Array.isArray(timeSlots)) {
      console.error('time_slots字段不是数组:', formValues);
      alert('表单数据异常: 时间段数据格式不正确');
      return;
    }

    // 检查每个时间段的有效性
    const invalidSlots = [];
    const validSlots = timeSlots.map((slot, index) => {
      if (!slot?.start || !slot?.end) {
        invalidSlots.push(`时间段 ${index + 1}: 缺少开始或结束时间`);
        return null;
      }

      try {
        const start = fromServerFormat(slot.start);
        const end = fromServerFormat(slot.end);

        if (!start || !end) {
          invalidSlots.push(`时间段 ${index + 1}: 时间格式无效`);
          return null;
        }

        const startDate = start.toDate();
        const endDate = end.toDate();

        if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
          invalidSlots.push(`时间段 ${index + 1}: 时间格式无效`);
          return null;
        }

        if (endDate <= startDate) {
          invalidSlots.push(`时间段 ${index + 1}: 结束时间必须晚于开始时间`);
          return null;
        }

        return {
          start,
          end,
          ...(slot.id && { id: slot.id })
        };
      } catch (error) {
        invalidSlots.push(`时间段 ${index + 1}: ${error.message}`);
        return null;
      }
    }).filter(Boolean);

    // 如果有无效时间段，显示详细错误
    if (invalidSlots.length > 0 || validSlots.length === 0) {
      const errorMessage = [
        '请修正以下问题:',
        ...invalidSlots,
        validSlots.length === 0 ? '至少需要一个有效时间段' : ''
      ].join('\n');

      console.error('时间段验证失败:', {
        formValues,
        invalidSlots,
        validSlots
      });

      Modal.error({
        title: '验证失败',
        content: errorMessage,
      });
      return;
    }

    const formData = {
      ...currentEvent,
      ...formValues,
      time_slots: validSlots
    };
    
    try {
      // 检查是否有重复时间段
      const slotTimes = formData.time_slots.map(slot => ({
        start: toServerFormat(slot.start),
        end: toServerFormat(slot.end)
      }));
      
      const hasDuplicates = slotTimes.some((slot, index) => 
        slotTimes.slice(index + 1).some(other => 
          slot.start === other.start && slot.end === other.end
        )
      );
      
      if (hasDuplicates) {
        Modal.error({
          title: '验证失败',
          content: '存在重复的时间段，请检查',
        });
        return;
      }

      // 如果是编辑模式且有修改过的时间段
      if (isEditing && modifiedSlots.length > 0) {
        // 只收集修改过的时间段
        const modifiedTimeSlots = formData.time_slots
          .filter(slot => slot.id && modifiedSlots.includes(slot.id))
          .map(slot => ({
            id: slot.id,
            start: toServerFormat(slot.start),
            end: toServerFormat(slot.end),
            description: slot.description
          }));
        
        if (modifiedTimeSlots.length > 0) {
          // 批量更新修改过的时间段
          await calendarApi.bulkUpdateTimeSlots(modifiedTimeSlots);
          queryClient.invalidateQueries(['trials']);
          setModifiedSlots([]);
        }
      }
      
      console.log('验证后的表单数据:', {
        ...formData,
        time_slots: formData.time_slots.map(slot => ({
          start: toServerFormat(slot.start),
          end: toServerFormat(slot.end),
          duration: slot.end - slot.start
        }))
      });
      await handleEventSubmit(formData);
      setIsEditing(false);
    } catch (error) {
      console.error('保存时间段失败:', error);
      Modal.error({
        title: '保存失败',
        content: error.message,
      });
    }
  };
  return (
    <Modal
      title={modalType === 'view' ? '查看试验排班' : '新建试验排班'}
      open={!!currentEvent}
      onCancel={() => {
        setIsEditing(false);
        // 不再调用setCurrentEvent(null)以保持模态框打开
      }}
      width={800}
      footer={
        modalType === 'view' ? (
          isEditing ? [
            <Button
              key="save"
              type="primary"
              onClick={handleManualSave}
            >
              {autoSaveStatus === 'saving' && '保存中...'}
              {autoSaveStatus === 'saved' && '已保存'}
              {autoSaveStatus === 'error' && '保存失败'}
              {!autoSaveStatus && '保存'}
            </Button>,
            <Button
              key="cancel"
              type="default"
              onClick={() => {
                setIsEditing(false);
                form.resetFields();
                // 不再调用setCurrentEvent(null)以保持模态框打开
              }}
            >
              取消
            </Button>
          ] : [
            <Button
              key="edit"
              type="primary"
              onClick={() => setIsEditing(true)}
            >
              编辑
            </Button>,
            <Button
              key="close"
              type="default"
              onClick={() => setCurrentEvent(null)}
            >
              关闭
            </Button>
          ]
        ) : [
          <Button
            key="save"
            type="primary"
            onClick={handleManualSave}
          >
            {autoSaveStatus === 'saving' && '保存中...'}
            {autoSaveStatus === 'saved' && '已保存'}
            {autoSaveStatus === 'error' && '保存失败'}
            {!autoSaveStatus && '保存'}
          </Button>
        ]
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <Form
          layout="vertical"
          form={form}
          initialValues={{ time_slots: [] }}
        >
          <Form.Item label="试验项目" required name="trial">
            <Select
              showSearch
              placeholder="搜索试验项目"
              filterOption={(input, option) =>
                `${option.label} ${option.value}`.toLowerCase().includes(input.toLowerCase())
              }
              options={trials.map(trial => ({
                value: trial.id,
                label: `${trial.title} (${trial.client})`,
                trialData: trial
              }))}
              optionFilterProp="label"
              onSearch={value => {
                // 触发API搜索
                getTrials({ search: value });
              }}
              loading={isTrialsLoading}
              onChange={(value, option) => {
                if (!option) {
                  setSelectedTrial(null);
                  return;
                }
                setSelectedTrial(option.trialData);
              }}
            />
          </Form.Item>

          {selectedTrial && (
            <TrialDetails selectedTrial={selectedTrial} />
          )}

          <Form.List name="time_slots">
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key, name, ...restField }) => (
                  <Space 
                    key={key} 
                    style={{ display: 'flex', marginBottom: 8 }} 
                    align="baseline"
                    onBlur={() => {
                      const slot = form.getFieldValue(['time_slots', name]);
                      if (slot?.id && !modifiedSlots.includes(slot.id)) {
                        setModifiedSlots([...modifiedSlots, slot.id]);
                      }
                      // 触发自动保存
                      if (autoSaveTimer) {
                        clearTimeout(autoSaveTimer);
                      }
                      setAutoSaveTimer(setTimeout(handleAutoSave, 5000));
                    }}
                    onChange={() => {
                      // 表单变更时重置自动保存计时器
                      if (autoSaveTimer) {
                        clearTimeout(autoSaveTimer);
                      }
                      setAutoSaveTimer(setTimeout(handleAutoSave, 5000));
                    }}
                  >
                    <Form.Item
                      {...restField}
                      name={[name, 'start']}
                      label="开始时间"
                      rules={[{ required: true, message: '请选择开始时间' }]}
                      getValueProps={(value) => ({ value: value ? fromServerFormat(value) : null })}
                    >
                      <DatePicker 
                        showTime 
                        format="YYYY-MM-DD HH:mm:ss"
                        disabled={!isEditing}
                        renderExtraFooter={() => (
                          <div style={{ padding: '8px', textAlign: 'center' }}>
                            <Button 
                              size="small" 
                              onClick={() => {
                                const current = form.getFieldValue(['time_slots', name, 'start']);
                                form.setFieldsValue({
                                  ['time_slots']: form.getFieldValue('time_slots').map((slot, i) => 
                                    i === name ? {
                                      ...slot,
                                      start: moment(current).subtract(1, 'month').toDate()
                                    } : slot
                                  )
                                });
                              }}
                            >
                              上个月
                            </Button>
                            <Button 
                              size="small" 
                              onClick={() => {
                                const current = form.getFieldValue(['time_slots', name, 'start']);
                                form.setFieldsValue({
                                  ['time_slots']: form.getFieldValue('time_slots').map((slot, i) => 
                                    i === name ? {
                                      ...slot,
                                      start: moment(current).add(1, 'month').toDate()
                                    } : slot
                                  )
                                });
                              }}
                              style={{ marginLeft: '8px' }}
                            >
                              下个月
                            </Button>
                          </div>
                        )}
                      />
                    </Form.Item>
                    <Form.Item
                      {...restField}
                      name={[name, 'end']}
                      label="结束时间"
                      rules={[{ required: true, message: '请选择结束时间' }]}
                      getValueProps={(value) => ({ value: value ? fromServerFormat(value) : null })}
                    >
                      <DatePicker 
                        showTime 
                        format="YYYY-MM-DD HH:mm:ss"
                        disabled={!isEditing}
                        renderExtraFooter={() => (
                          <div style={{ padding: '8px', textAlign: 'center' }}>
                            <Button 
                              size="small" 
                              onClick={() => {
                                const current = form.getFieldValue(['time_slots', name, 'end']);
                                form.setFieldsValue({
                                  ['time_slots']: form.getFieldValue('time_slots').map((slot, i) => 
                                    i === name ? {
                                      ...slot,
                                      end: moment(current).subtract(1, 'month').toDate()
                                    } : slot
                                  )
                                });
                              }}
                            >
                              上个月
                            </Button>
                            <Button 
                              size="small" 
                              onClick={() => {
                                const current = form.getFieldValue(['time_slots', name, 'end']);
                                form.setFieldsValue({
                                  ['time_slots']: form.getFieldValue('time_slots').map((slot, i) => 
                                    i === name ? {
                                      ...slot,
                                      end: moment(current).add(1, 'month').toDate()
                                    } : slot
                                  )
                                });
                              }}
                              style={{ marginLeft: '8px' }}
                            >
                              下个月
                            </Button>
                          </div>
                        )}
                      />
                    </Form.Item>
                    <Form.Item
                      {...restField}
                      name={[name, 'description']}
                      label="描述"
                    >
                      <Input.TextArea rows={1} disabled={!isEditing} />
                    </Form.Item>
                    {(() => {
                      const slot = form.getFieldValue(['time_slots', name]);
                      return (
                        <ConfirmModal
                          title="确认删除"
                          content={`确定要删除时间段 ${moment(slot?.start).format('YYYY-MM-DD HH:mm')} 到 ${moment(slot?.end).format('YYYY-MM-DD HH:mm')} 吗？`}
                          okText="删除"
                          cancelText="取消"
                          danger={true}
                          onOk={async () => {
                            try {
                              if (slot?.id) {
                                await calendarApi.deleteTimeSlot(slot.id);
                                queryClient.invalidateQueries(['trials']);
                                if (typeof setDefaultEvents === 'function') {
                                  setDefaultEvents(prev => 
                                    prev.filter(e => e.id !== `slot_${slot.id}`)
                                  );
                                }
                              }
                              remove(name);
                            } catch (error) {
                              console.error('删除操作出错:', error);
                              Modal.error({
                                title: '删除失败',
                                content: error.message || '删除时间段时出错',
                              });
                              throw error;
                            }
                          }}
                        >
                          {isEditing ? (
                            <MinusCircleOutlined 
                              style={{ fontSize: '16px', color: '#ff4d4f' }}
                              onClick={(e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                if (!slot?.start || !slot?.end) {
                                  Modal.error({
                                    title: '无效时间段',
                                    content: '无法删除无效的时间段',
                                  });
                                }
                              }}
                            />
                          ) : <span />}
                        </ConfirmModal>
                      );
                    })()}
                  </Space>
                ))}
                <Form.Item>
                  {isEditing && (
                    <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                      添加时间段
                    </Button>
                  )}
                </Form.Item>
              </>
            )}
          </Form.List>
        </Form>
      </div>
    </Modal>
  );
};

export default EventModal;
