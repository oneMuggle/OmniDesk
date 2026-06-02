/* eslint-env node */
// Mock for jspdf - prevents ESM parsing issues in Jest
module.exports = class jsPDF {
  constructor() {}
  save() {}
  addPage() {}
  text() {}
  output() { return ''; }
  internal = { pageSize: { getWidth: () => 595, getHeight: () => 842 } };
};
