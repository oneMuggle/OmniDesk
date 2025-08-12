import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import api from '../api/axiosConfig';
import TableOfContents from './TableOfContents';
import ChapterView from './ChapterView';
import complianceApi from '../api/compliance'; // 导入合规API
import './BookReaderPage.css'; // Use a dedicated CSS file for the independent reader page

const BookReaderPage = () => {
    const { bookId } = useParams();
    const [book, setBook] = useState(null);
    const [selectedChapter, setSelectedChapter] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [complianceIssues, setComplianceIssues] = useState([]); // 新增合规问题状态

    useEffect(() => {
        const fetchData = async () => {
            if (!bookId) return;
            try {
                const [bookResponse, complianceResponse] = await Promise.all([
                    api.get(`/api/documents/books/${bookId}/`),
                    complianceApi.getAllComplianceIssues({ document_book: bookId }) // 获取与书籍相关的合规问题
                ]);
                setBook(bookResponse.data);
                setComplianceIssues(complianceResponse.data.results || complianceResponse.data);

                if (bookResponse.data.chapters && bookResponse.data.chapters.length > 0) {
                    // Select the first chapter by default
                    setSelectedChapter(bookResponse.data.chapters[0]);
                }
                setLoading(false);
            } catch (err) {
                setError('Failed to load data.');
                setLoading(false);
                console.error('Error fetching data:', err);
            }
        };

        fetchData();
    }, [bookId]);

    const handleChapterSelect = (chapter) => {
        setSelectedChapter(chapter);
    };


    if (loading) {
        return <div>Loading...</div>;
    }

    if (error) {
        return <div>{error}</div>;
    }

    return (
        <div className="book-reader-page"> {/* New class for the independent reader page */}
            <div className="table-of-contents-container">
                <TableOfContents 
                    chapters={book.chapters} 
                    onChapterSelect={handleChapterSelect}
                    selectedChapterId={selectedChapter?.id}
                />
            </div>
            <div className="chapter-view-container">
                {selectedChapter ? (
                    <ChapterView
                        chapter={selectedChapter}
                        complianceIssues={complianceIssues.filter(issue =>
                            issue.document_book === bookId && // 确保是当前书籍的合规问题
                            (issue.location.startsWith(`Chapter ${selectedChapter.order}`) || // 检查章节位置
                             issue.location.includes(selectedChapter.title)) // 或者包含章节标题
                        )}
                    />
                ) : (
                    <div>Please select a chapter to read.</div>
                )}
            </div>
        </div>
    );
};

export default BookReaderPage;