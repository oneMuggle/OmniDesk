import React, { useState, useEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom'; // Import Link and useLocation
import api from '../api/axiosConfig';
import './ChapterView.css';
import Commenting from './Commenting';
import AnnotationHandler from './AnnotationHandler';
const ChapterView = ({ chapter }) => {
    const [chapterDetails, setChapterDetails] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const contentRef = useRef(null); // Ref for the content div
    const location = useLocation();

    useEffect(() => {
        if (!chapter) return;

        const fetchChapterDetails = async () => {
            setLoading(true);
            try {
                const response = await api.get(`/api/documents/chapters/${chapter.id}/`);
                setChapterDetails(response.data);
                setLoading(false);
            } catch (err) {
                setError('Failed to load chapter details.');
                setLoading(false);
            }
        };

        fetchChapterDetails();
    }, [chapter]);

    // Effect to trigger MathJax typesetting
    useEffect(() => {
        if (contentRef.current && window.MathJax) {
            // Ensure MathJax is ready and then typeset the content
            window.MathJax.typesetPromise([contentRef.current]).catch((err) => console.error("MathJax typesetting failed:", err));
        }
    }, [chapterDetails]); // Re-run when chapterDetails change

    // Effect to handle scrolling to headings based on URL hash
    useEffect(() => {
        if (location.hash && !loading) {
            const id = location.hash.replace('#', '');
            // We need to find the element within the rendered HTML
            const element = contentRef.current ? contentRef.current.querySelector(`#${id}`) : null;
            if (element) {
                element.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    }, [location.hash, loading, chapterDetails]);

    if (loading) {
        return <div>正在加载章节...</div>;
    }

    if (error) {
        return <div>{error}</div>;
    }

    if (!chapterDetails) {
        return <div>没有章节数据。</div>;
    }

    return (
        <div className="chapter-view">
            <AnnotationHandler chapterId={chapterDetails.id}>
                {/* Render content directly, MathJax will process it */}
                <div
                    ref={contentRef} // Attach ref here
                    className="chapter-content"
                    dangerouslySetInnerHTML={{ __html: chapterDetails.content_html || '' }} // Ensure it's a string
                />
            </AnnotationHandler>
            <Commenting chapterId={chapterDetails.id} comments={chapterDetails.comments} />
            {/* Add Edit Chapter button */}
            <Link
                to={`/books/${chapterDetails.book}/chapters/${chapterDetails.id}/edit`}
                className="edit-chapter-button"
            >
                编辑章节
            </Link>
        </div>
    );
};

export default ChapterView;