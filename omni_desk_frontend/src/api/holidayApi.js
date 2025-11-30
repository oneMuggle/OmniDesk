// 模拟后端数据
let holidays = [
  { id: 1, name: '元旦', start_date: '2024-01-01', end_date: '2024-01-01' },
  { id: 2, name: '春节', start_date: '2024-02-10', end_date: '2024-02-17' },
  { id: 3, name: '劳动节', start_date: '2024-05-01', end_date: '2024-05-03' },
  { id: 4, name: '国庆节', start_date: '2024-10-01', end_date: '2024-10-07' },
];

let nextId = 5;

export const holidayApi = {
  getHolidays: () => {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve([...holidays]);
      }, 500);
    });
  },

  createHoliday: (holidayData) => {
    return new Promise((resolve) => {
      setTimeout(() => {
        const newHoliday = {
          id: nextId++,
          ...holidayData,
        };
        holidays.push(newHoliday);
        resolve(newHoliday);
      }, 500);
    });
  },

  deleteHoliday: (holidayId) => {
    return new Promise((resolve) => {
      setTimeout(() => {
        holidays = holidays.filter(h => h.id !== holidayId);
        resolve();
      }, 500);
    });
  },

  updateHoliday: (holidayId, holidayData) => {
    return new Promise((resolve) => {
      setTimeout(() => {
        const index = holidays.findIndex(h => h.id === holidayId);
        if (index !== -1) {
          holidays[index] = { ...holidays[index], ...holidayData };
          resolve(holidays[index]);
        }
      }, 500);
    });
  },
};