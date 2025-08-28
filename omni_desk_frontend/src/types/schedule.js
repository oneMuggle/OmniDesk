/**
 * @typedef {'TRIAL' | 'SCHEDULE'} EventType
 */

/**
 * @typedef {object} ScheduleEvent
 * @property {string} id - 事件的唯一标识符
 * @property {string} title - 事件的标题
 * @property {Date} start - 事件的开始时间
 * @property {Date} end - 事件的结束时间
 * @property {EventType} type - 事件的类型 ('TRIAL' 或 'SCHEDULE')
 * @property {boolean} [allDay] - 是否为全天事件
 * @property {object} [extendedProps] - 扩展属性，用于存储特定于事件类型的数据
 */