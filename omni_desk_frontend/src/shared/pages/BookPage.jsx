import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import api from '../api/axiosConfig';
import TableOfContents from '../components/TableOfContents';
import ChapterView from '../components/ChapterView';
import './BookPage.css';

const BookPage = () => {
    const { bookId } = useParams();
    const [book, setBook] = useState(null);
    const [selectedChapter, setSelectedChapter] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchBook = async () => {
            if (!bookId) return;
            try {
                const response = await api.get(`/api/documents/books/${bookId}/`);
                setBook(response.data);
                if (response.data.chapters && response.data.chapters.length > 0) {
                    // Select the first chapter by default
                    setSelectedChapter(response.data.chapters[0]);
                }
                setLoading(false);
            } catch (err) {
                setError('Failed to load the book.');
                setLoading(false);
            }
        };

        fetchBook();
    }, [bookId]);

    const handleChapterSelect = (chapter) => {
        setSelectedChapter(chapter);
    };

    const handleExportMarkdown = async () => {
        try {
            const response = await api.get(`/api/documents/books/${bookId}/export_markdown/`, {
                responseType: 'blob', // Important: responseType must be 'blob' for file downloads
            });

            // Create a Blob from the response data
            const blob = new Blob([response.data], { type: 'text/markdown' });
            // Create a link element
            const link = document.createElement('a');
            // Set the download attribute and href
            link.href = URL.createObjectURL(blob);
            link.download = `${book.title}.md`; // Set the filename
            // Append to the DOM and trigger click
            document.body.appendChild(link);
            link.click();
            // Clean up
            document.body.removeChild(link);
            URL.revokeObjectURL(link.href);
        } catch (error) {
            console.error('Error exporting markdown:', error);
            alert('导出Markdown失败，请稍后再试。');
        }
    };

    if (loading) {
        return <div>Loading...</div>;
    }

    if (error) {
        return <div>{error}</div>;
    }

    return (
        <div className="book-page">
            <div className="table-of-contents-container">
                <TableOfContents 
                    chapters={book.chapters} 
                    onChapterSelect={handleChapterSelect}
                    selectedChapterId={selectedChapter?.id}
                />
            </div>
            <div className="chapter-view-container">
                {selectedChapter ? (
                    <ChapterView chapter={selectedChapter} />
                ) : (
                    <div>Please select a chapter to read.</div>
                )}
            </div>
            <button onClick={handleExportMarkdown} className="export-markdown-button">
                导出Markdown
            </button>
        </div>
    );
};

export default BookPage;