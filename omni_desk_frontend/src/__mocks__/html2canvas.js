/* eslint-env node */
// Mock for html2canvas
module.exports = async function html2canvas() {
  return { toDataURL: () => 'data:image/png;base64,mock' };
};
