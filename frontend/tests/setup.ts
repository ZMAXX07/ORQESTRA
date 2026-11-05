import '@testing-library/jest-dom';

// Polyfill window.URL createObjectURL and revokeObjectURL for PDF download testing
if (typeof window !== 'undefined') {
  if (!window.URL.createObjectURL) {
    window.URL.createObjectURL = () => 'blob:mock-url';
  }
  if (!window.URL.revokeObjectURL) {
    window.URL.revokeObjectURL = () => {};
  }

  // Prevent JSDOM unhandled navigation error when simulated download links with download attribute are clicked
  const originalClick = HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click = function (this: HTMLAnchorElement) {
    if (this.hasAttribute('download')) {
      return;
    }
    return originalClick.call(this);
  };
}
