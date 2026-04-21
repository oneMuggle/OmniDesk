import { useState, useEffect, useRef } from 'react';
import PropTypes from 'prop-types';
import { Link, useLocation } from 'react-router-dom';
import { Alert, Typography, Collapse, Button } from 'antd';
import api from '../api/axiosConfig';
import './ChapterView.css';
import Commenting from './Commenting';
import AnnotationHandler from './AnnotationHandler';

const { Text } = Typography;
const { Panel } = Collapse;

const ChapterView = ({ chapter, complianceIssues = [] }) => {
    const [chapterDetails, setChapterDetails] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const contentRef = useRef(null);
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

    useEffect(() => {
        if (contentRef.current && window.MathJax) {
            window.MathJax.typesetPromise([contentRef.current]).catch((err) => console.error("MathJax typesetting failed:", err));
        }
    }, [chapterDetails]);

    useEffect(() => {
        if (location.hash && !loading) {
            const id = location.hash.replace('#', '');
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
            {complianceIssues && complianceIssues.length > 0 && (
                <Alert
                    message="本章存在合规问题"
                    type="warning"
                    className="compliance-alert"
                >
                    <Collapse accordion>
                        {complianceIssues.map((issue) => (
                            <Panel
                                header={`${issue.issue_type} - ${issue.description}`}
                                key={issue.id}
                                extra={
                                    <Text type="secondary">
                                        {issue.location} | {issue.severity} | {issue.status}
                                    </Text>
                                }
                            >
                                <Text>建议修改: {issue.suggested_fix || '无'}</Text>
                            </Panel>
                        ))}
                    </Collapse>
                </Alert>
            )}

            <AnnotationHandler chapterId={chapterDetails.id}>
                <div
                    ref={contentRef}
                    className="chapter-content"
                    dangerouslySetInnerHTML={{ __html: chapterDetails.content_html || '' }}
                />
            </AnnotationHandler>
            <Commenting chapterId={chapterDetails.id} comments={chapterDetails.comments} />
            <Link
                to={`/books/${chapterDetails.book}/chapters/${chapterDetails.id}/edit`}
                className="edit-chapter-button"
            >
                <Button type="primary">编辑章节</Button>
            </Link>
        </div>
    );
};

ChapterView.propTypes = {
  chapter: PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  }).isRequired,
  complianceIssues: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.number.isRequired,
    issue_type: PropTypes.string,
    description: PropTypes.string,
    location: PropTypes.string,
    severity: PropTypes.string,
    status: PropTypes.string,
    suggested_fix: PropTypes.string,
  })),
};

export default ChapterView;
