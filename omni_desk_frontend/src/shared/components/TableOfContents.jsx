import PropTypes from 'prop-types';
import { Menu } from 'antd';
import { useNavigate } from 'react-router-dom';
import './TableOfContents.css';

const { SubMenu } = Menu;

const TableOfContents = ({ chapters, onChapterSelect, selectedChapterId = null }) => {
    const navigate = useNavigate();

    const handleHeadingClick = (chapter, headingId) => {
        onChapterSelect(chapter);
        // Use navigate to change the hash, which will be caught by ChapterView
        navigate(`#${headingId}`);
    };

    const renderHeadings = (chapter, headings) => {
        return headings.map(heading => {
            if (heading.children && heading.children.length > 0) {
                return (
                    <SubMenu key={`heading-${chapter.id}-${heading.id}`} title={heading.title}>
                        {renderHeadings(chapter, heading.children)}
                    </SubMenu>
                );
            }
            return (
                <Menu.Item key={`heading-${chapter.id}-${heading.id}`} onClick={() => handleHeadingClick(chapter, heading.id)}>
                    {heading.title}
                </Menu.Item>
            );
        });
    };

    return (
        <div className="table-of-contents">
            <h2>目录</h2>
            <Menu
                mode="inline"
                selectedKeys={selectedChapterId ? [`chapter-${selectedChapterId}`] : []}
                style={{ borderRight: 0 }}
            >
                {chapters.sort((a, b) => a.order - b.order).map(chapter => {
                    if (chapter.heading_structure && chapter.heading_structure.length > 0) {
                        return (
                            <SubMenu key={`chapter-${chapter.id}`} title={chapter.title} onTitleClick={() => onChapterSelect(chapter)}>
                                {renderHeadings(chapter, chapter.heading_structure)}
                            </SubMenu>
                        );
                    }
                    return (
                        <Menu.Item key={`chapter-${chapter.id}`} onClick={() => onChapterSelect(chapter)}>
                            {chapter.title}
                        </Menu.Item>
                    );
                })}
            </Menu>
        </div>
    );
};

TableOfContents.propTypes = {
  chapters: PropTypes.array.isRequired,
  onChapterSelect: PropTypes.func.isRequired,
  selectedChapterId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
};


export default TableOfContents;