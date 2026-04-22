const PageLayout = ({ title, children, extra }) => {
  return (
    <div style={{ padding: 'var(--spacing-lg)' }}>
      {title && (
        <div style={{ marginBottom: 'var(--spacing-lg)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0 }}>{title}</h2>
          {extra}
        </div>
      )}
      {children}
    </div>
  );
};

export default PageLayout;