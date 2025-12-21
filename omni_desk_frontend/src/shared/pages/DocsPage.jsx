import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import './DocsPage.css';

const DocsPage = () => {
  const [markdown, setMarkdown] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchMarkdown = async () => {
      try {
        const response = await fetch('/docs/cdepsio6.md');
        if (!response.ok) {
          throw new Error(`Failed to fetch markdown: ${response.status}`);
        }
        const text = await response.text();
        setMarkdown(text);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchMarkdown();
  }, []);

  return (
    <div className="docs-container">
      {loading ? (
        <div className="loading-indicator">Loading...</div>
      ) : error ? (
        <div className="error-message">⚠️ {error}</div>
      ) : (
        <ReactMarkdown>{markdown}</ReactMarkdown>
      )}
    </div>
  );
};

export default DocsPage;
