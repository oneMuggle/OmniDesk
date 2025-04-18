import React, { useEffect, useState } from 'react';
import { Button, Form, Input, Space, DatePicker, Modal } from 'antd';
import { MinusCircleOutlined, PlusOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import { fromServerFormat, toServerFormat } from '../../../utils/dateUtils';
import dayjs from 'dayjs';

const TimeSlotForm = ({
  form,
  isEditing,
  isGuest = false,
  modifiedSlots,
  setModifiedSlots,
  setDefaultEvents,
  queryClient,
  calendarApi,
}) => {
  // 直接使用父组件传入的form prop

  // 用于确认删除对话框的状态
  const [deleteConfirmVisible, setDeleteConfirmVisible] = useState(false);
  const [slotToDelete, setSlotToDelete] = useState(null);
  const [indexToDelete, setIndexToDelete] = useState(null);
  const [removeFunction, setRemoveFunction] = useState(null);

  // 打开确认删除对话框
  const showDeleteConfirm = (slot, name, remove) => {
    setSlotToDelete(slot);
    setIndexToDelete(name);
    setRemoveFunction(() => remove);
    setDeleteConfirmVisible(true);
  };

  // 删除时间段
  const handleDeleteConfirm = async () => {
    if (!slotToDelete || typeof indexToDelete !== 'number' || !removeFunction) {
      console.error('删除信息不完整', { slotToDelete, indexToDelete, removeFunction });
      return;
    }

    try {
      if (slotToDelete.id) {
        console.log('[DEBUG] 删除时间段，原始ID:', slotToDelete.id);
        
        // 验证ID格式
        const idStr = String(slotToDelete.id);
        const isValidId = idStr.startsWith('slot_') || idStr.startsWith('trial-') || !isNaN(idStr);
        if (!isValidId) {
          throw new Error(`无效的时间段ID格式: ${slotToDelete.id}`);
        }

        // 调试日志 - 删除前检查表单状态
        const beforeSlots = form.getFieldValue('time_slots') || [];
        console.log('[DEBUG] 删除前时间段:', 
          beforeSlots.map(s => ({ 
            id: s.id, 
            start_time: s.start_time, 
            end_time: s.end_time,
            type: typeof s.id
          }))
        );
        console.log('[DEBUG] 删除前 modifiedSlots:', modifiedSlots);
        
        // 删除时间段
        await calendarApi.deleteTimeSlot(slotToDelete.id);
        
        // 从被修改的时间段列表中删除当前时间段
        if (modifiedSlots.some(s => s.id === slotToDelete.id)) {
          const newModifiedSlots = modifiedSlots.filter(s => s.id !== slotToDelete.id);
          console.log('[DEBUG] 从 modifiedSlots 中移除 ID:', slotToDelete.id);
          console.log('[DEBUG] 新的 modifiedSlots:', newModifiedSlots);
          setModifiedSlots(newModifiedSlots);
        }
        
        queryClient.invalidateQueries(['trials']);
        console.log('[DEBUG] 删除成功，ID:', slotToDelete.id);
      } else {
        console.log('删除新添加的时间段');
      }
      
      // 调用删除函数
      removeFunction(indexToDelete);
      
      // 删除后检查表单状态
      setTimeout(() => {
        const afterSlots = form.getFieldValue('time_slots') || [];
        console.log('[DEBUG] 删除后时间段:', 
          afterSlots.map(s => ({ id: s.id, start_time: s.start_time, end_time: s.end_time }))
        );
      }, 0);
      
      setDeleteConfirmVisible(false);
    } catch (error) {
      console.error('删除时间段失败:', error);
      Modal.error({
        title: '删除失败',
        content: error.message,
      });
    }
  };

  // 取消删除
  const handleDeleteCancel = () => {
    setDeleteConfirmVisible(false);
    setSlotToDelete(null);
    setIndexToDelete(null);
    setRemoveFunction(null);
  };

  // 监听time_slots字段变化并初始化timeRange
  useEffect(() => {
    const initializeTimeSlots = () => {
      const timeSlots = form.getFieldValue('time_slots') || [];
      console.log('Initializing time slots:', timeSlots);
      
      if (timeSlots.length > 0) {
            const updatedTimeSlots = timeSlots.map(slot => {
              try {
                // 处理数组格式的时间范围
                if (Array.isArray(slot?.timeRange)) {
                  return {
                    ...slot,
                    timeRange: slot.timeRange,
                    start_time: slot.start_time,
                    end_time: slot.end_time
                  };
                }
                
                // 处理单独的开始/结束时间
                if (slot?.start_time || slot?.end_time) {
                  const startTime = slot.start_time 
                    ? (typeof slot.start_time === 'string' 
                      ? dayjs(slot.start_time) 
                      : slot.start_time)
                    : null;
                  const endTime = slot.end_time 
                    ? (typeof slot.end_time === 'string' 
                      ? dayjs(slot.end_time) 
                      : slot.end_time)
                    : null;
              
              console.log('Processing slot:', {
                id: slot.id,
                originalStart: slot.start_time,
                originalEnd: slot.end_time,
                convertedStart: startTime?.format(),
                convertedEnd: endTime?.format()
              });
              
              return {
                ...slot,
                timeRange: [startTime, endTime]
              };
            }
            return slot;
          } catch (error) {
            console.error('Error processing time slot:', error);
            return slot;
          }
        });
        
        console.log('Updated time slots with timeRange:', updatedTimeSlots);
        form.setFieldsValue({ time_slots: updatedTimeSlots });
      }
    };

    // 初始加载时执行
    initializeTimeSlots();
    
    // 安全地监听time_slots字段变化
    let unsubscribe = () => {};
    if (form && typeof form.onFieldsChange === 'function') {
      unsubscribe = form.onFieldsChange((changedFields) => {
        if (changedFields.some(field => field.name.includes('time_slots'))) {
          initializeTimeSlots();
        }
      });
    } else if (form && typeof form.watch === 'function') {
      // 兼容其他表单库的watch方法
      unsubscribe = form.watch('time_slots', initializeTimeSlots);
    } else {
      console.warn('Form instance does not support field change listening');
    }
    
    return unsubscribe;
  }, [form]);

  const handleTimeSlotChange = (index, field, value) => {
    console.log('Time slot changed - index:', index, 'field:', field, 'value:', value);
    console.log('Before update:', form.getFieldValue('time_slots'));
    const timeSlots = form.getFieldValue('time_slots') || [];
    const newSlots = [...timeSlots];
    
    if (field === 'timeRange') {
      newSlots[index] = {
        ...newSlots[index],
        start_time: value?.[0] ? toServerFormat(value[0]) : null,
        end_time: value?.[1] ? toServerFormat(value[1]) : null,
        timeRange: value
      };
    } else {
      newSlots[index] = {
        ...newSlots[index],
        [field]: value
      };
    }

    form.setFieldsValue({ time_slots: newSlots });
    console.log('After update:', newSlots);
    
    // 对于已有时间段(id不为null)，标记为修改
    if (newSlots[index]?.id) {
      const slotId = newSlots[index].id;
      console.log('[DEBUG] 检查时间段更新:', {
        slotId,
        modifiedSlots
      });
      
      if (!modifiedSlots.includes(slotId)) {
        setModifiedSlots([...modifiedSlots, slotId]);
        console.log('[DEBUG] 添加到modifiedSlots:', slotId);
      }
    }
  };

  return (
    <>
      <Form.Item label="时间段" required>
        <Form.List name="time_slots">
          {(fields, { add, remove }) => {
            // console.log('Form.List fields:', fields);
            return (
              <>
                {fields.map(({ key, name, ...restField }) => {
                  const slot = form.getFieldValue(['time_slots', name]);
                  // console.log('Current slot data:', slot);
                  
                  const startTime = slot?.start_time ? (typeof slot.start_time === 'string' ? fromServerFormat(slot.start_time) : slot.start_time) : null;
                  const endTime = slot?.end_time ? (typeof slot.end_time === 'string' ? fromServerFormat(slot.end_time) : slot.end_time) : null;
                  const timeRange = slot?.timeRange || [startTime, endTime];
                  
                  console.log('Time slot display values:', {
                    rawStart: slot?.start_time,
                    rawEnd: slot?.end_time,
                    startTime: startTime?.format(),
                    endTime: endTime?.format(),
                    timeRange: timeRange?.map(t => t?.format())
                  });
                  
                  // console.log('Raw slot data:', slot);
                  // console.log('Dayjs converted:', { startTime, endTime });
                  // console.log('Processed times:', {
                  //   startTime: startTime?.format('YYYY-MM-DD HH:mm:ss'),
                  //   endTime: endTime?.format('YYYY-MM-DD HH:mm:ss'),
                  //   startTimeIsValid: startTime?.isValid(),
                  //   endTimeIsValid: endTime?.isValid()
                  // });

                  return (
                    <Space
                      key={key}
                      style={{ display: 'flex', marginBottom: 8 }}
                      align="baseline"
                    >
                      <Form.Item
                        {...restField}
                        name={[name, 'timeRange']}
                        initialValue={timeRange}
                        valuePropName="value"
                          getValueProps={(value) => {
                            console.log('Time slot value props:', value);
                            if (!value) return { value: [null, null] };
                            
                            // 处理数组格式的时间范围
                            if (Array.isArray(value)) {
                              return {
                                value: value.map(item => {
                                  if (!item) return null;
                                  if (dayjs.isDayjs(item)) return item;
                                  if (typeof item === 'string') {
                                    try {
                                      // 优先尝试解析ISO 8601格式
                                      if (item.includes('T')) {
                                        return dayjs(item);
                                      }
                                      // 否则尝试使用fromServerFormat
                                      return fromServerFormat(item);
                                    } catch (e) {
                                      console.error('时间格式转换失败:', item, e);
                                      return null;
                                    }
                                  }
                                  return null;
                                })
                              };
                            }
                            
                            // 处理对象格式(含start_time/end_time)
                            if (value.start_time || value.end_time) {
                              return {
                                value: [
                                  value.start_time ? 
                                    (typeof value.start_time === 'string' ? 
                                      dayjs(value.start_time) : 
                                      value.start_time) : 
                                    null,
                                  value.end_time ? 
                                    (typeof value.end_time === 'string' ? 
                                      dayjs(value.end_time) : 
                                      value.end_time) : 
                                    null
                                ]
                              };
                            }
                            
                            return { value: [null, null] };
                          }}
                        rules={[
                          {
                            required: true,
                            message: '请选择时间段',
                            validator: (_, value) => {
                              if (!value || !value[0] || !value[1] || 
                                  !value[0].isValid() || !value[1].isValid()) {
                                return Promise.reject('请选择完整时间段');
                              }
                              return Promise.resolve();
                            }
                          }
                        ]}
                      >
                        <DatePicker.RangePicker
                          showTime={{ 
                            format: 'HH:mm',
                            defaultValue: [dayjs('00:00', 'HH:mm'), dayjs('23:59', 'HH:mm')]
                          }}
                          format="YYYY-MM-DD HH:mm"
                          minuteStep={15}
                          disabled={!isEditing || isGuest}
                          value={timeRange}
                          onChange={(value) => {
                            console.log('DatePicker onChange value:', value);
                            handleTimeSlotChange(name, 'timeRange', value);
                          }}
                          onOpenChange={(open) => {
                            if (open) {
                              console.log('DatePicker current value:', timeRange);
                            }
                          }}
                          style={{ width: '100%' }}
                          placeholder={['开始时间', '结束时间']}
                          allowClear={false}
                          allowEmpty={[true, true]}
                        />
                      </Form.Item>

                      <Form.Item
                        {...restField}
                        name={[name, 'description']}
                      >
                        <Input
                          placeholder="描述(可选)"
                          disabled={!isEditing || isGuest}
                          onChange={(e) => 
                            handleTimeSlotChange(name, 'description', e.target.value)
                          }
                        />
                      </Form.Item>

                      {isEditing && !isGuest && (
                        <MinusCircleOutlined
                          onClick={() => {
                            console.log('删除按钮被点击');
                            showDeleteConfirm(slot, name, remove);
                          }}
                        />
                      )}
                    </Space>
                  );
                })}

                {isEditing && !isGuest && (
                  <Form.Item>
                    <Button
                      type="dashed"
                      onClick={() => {
                        add({
                          id: null,
                          start_time: null,
                          end_time: null,
                          description: ''
                        });
                      }}
                      block
                      icon={<PlusOutlined />}
                    >
                      添加时间段
                    </Button>
                  </Form.Item>
                )}
              </>
            );
          }}
        </Form.List>
      </Form.Item>

      {/* 确认删除对话框 */}
      <Modal
        title="确认删除"
        open={deleteConfirmVisible}
        onOk={handleDeleteConfirm}
        onCancel={handleDeleteCancel}
        okText="确定"
        cancelText="取消"
      >
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <ExclamationCircleOutlined style={{ color: '#faad14', fontSize: '22px', marginRight: '16px' }} />
          <span>确定要删除这个时间段吗？</span>
        </div>
      </Modal>
    </>
  );
};

export default TimeSlotForm;
