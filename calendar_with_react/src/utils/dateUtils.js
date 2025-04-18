import dayjs from 'dayjs';
import utc from 'dayjs-plugin-utc';

dayjs.extend(utc);

// 1. 日期解析 - 处理多种输入类型
export const parseDate = (input) => {
  if (!input) return null;
  
  // 处理moment对象
  if (dayjs.isDayjs(input)) {
    return input.isValid() ? input : null;
  }
  
  // 处理Date对象
  if (input instanceof Date) {
    return isNaN(input.getTime()) ? null : dayjs(input);
  }
  
  // 处理时间戳
  if (typeof input === 'number') {
    const date = dayjs.unix(input);
    return date.isValid() ? date : null;
  }
  
  // 处理字符串
  const date = dayjs(input);
  return date.isValid() ? date : null;
};

// 2. 日期格式化
export const formatDate = (date, format = 'YYYY-MM-DD') => {
  const parsed = parseDate(date);
  return parsed ? parsed.format(format) : '';
};

// 3. 日期验证
export const isValidDate = (date) => {
  return !!parseDate(date);
};

// 4. 转换为后端格式 (ISO 8601 with timezone)
export const toServerFormat = (date) => {
  const parsed = parseDate(date);
  return parsed ? parsed.utc().format() : null; // 使用ISO8601 UTC格式
};

// 5. 从后端格式解析 (支持带时区和数组输入)
export const fromServerFormat = (dateInput) => {
  if (!dateInput) return null;
  
  // 处理数组输入
  if (Array.isArray(dateInput)) {
    return dateInput.map(d => {
      try {
        return dayjs(d).utc().local();
      } catch (e) {
        console.error('Invalid date format in array:', d);
        return null;
      }
    });
  }
  
  // 处理单个日期输入
  try {
    return dayjs(dateInput).utc().local();
  } catch (e) {
    console.error('Invalid date format:', dateInput);
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
