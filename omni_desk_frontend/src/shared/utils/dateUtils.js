import dayjs from 'dayjs';
import { logger } from './logger';
// import utc from 'dayjs-plugin-utc'; // 禁用 utc 插件，用于排查问题
// import timezone from 'dayjs/plugin/timezone'; // 禁用 timezone 插件，用于排查问题

// dayjs.extend(utc); // 禁用 utc 插件，用于排查问题
// dayjs.extend(timezone); // 禁用 timezone 插件，用于排查问题

// 确保所有日期都是 dayjs 实例
const ensureDayjs = (date) => {
  if (dayjs.isDayjs(date)) { // 检查是否已经是 dayjs 实例
    return date;
  }
  if (date instanceof Date) { // 检查是否是原生 Date 对象
    return dayjs(date);
  }
  if (typeof date === 'string') { // 检查是否是字符串
    return dayjs(date);
  }
  // 对于 null/undefined 或其他未知类型，返回一个有效的 dayjs 实例或 null
  return date === null || date === undefined ? null : dayjs(date);
};

// 1. 日期解析 - 处理多种输入类型
export const parseDate = (input) => {
  try {
    const parsed = ensureDayjs(input);
    return isValidDate(parsed) ? parsed : null;
  } catch {
    return null;
 }
};

// 2. 日期格式化
export const formatDate = (date, format = 'YYYY-MM-DD') => {
  const parsed = parseDate(date);
  return parsed ? parsed.format(format) : '';
};

// 3. 日期验证
export const isValidDate = (date) => {
  try {
    const parsed = ensureDayjs(date);
    return parsed && typeof parsed.isValid === 'function' && parsed.isValid();
  } catch {
    return false;
  }
};

// 4. 转换为后端格式 (ISO 8601 with timezone)
export const toServerFormat = (date) => {
  const parsed = ensureDayjs(date);
  // 直接格式化为 ISO 8601 字符串，不进行 UTC 转换
  return parsed ? parsed.format() : null;
};

// 5. 从后端格式解析 (直接解析，不进行时区转换)
export const fromServerFormat = (dateInput) => {
  if (!dateInput) return null;
  
  // 处理数组输入
  if (Array.isArray(dateInput)) {
    return dateInput.map(d => {
      try {
        // 直接解析，不进行时区转换
        return dayjs(d);
      } catch (e) {
        logger.error('Invalid date format in array:', d);
        return null;
      }
    });
  }
  
  // 处理单个日期输入
  try {
    // 直接解析，不进行时区转换
    return dayjs(dateInput);
  } catch (e) {
    logger.error('Invalid date format:', dateInput);
    return null;
  }
};

// 6. 日期比较
export const isBefore = (date, compareDate) => {
  const d1 = parseDate(date);
  const d2 = parseDate(compareDate);
  return d1 && d2 ? d1.isBefore(d2) : false;
};

// 7. 日期加减
export const addDays = (date, days) => {
  const parsed = parseDate(date);
  return parsed ? parsed.add(days, 'days') : null;
};

export const validateEndDate = (date) => {
  return isValidDate(date) ? date : null;
};

export const validateStartDate = (date) => {
  return isValidDate(date) ? date : null;
};
