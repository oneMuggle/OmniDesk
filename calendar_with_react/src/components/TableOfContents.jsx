import React from 'react';
import './TableOfContents.css';

const TableOfContents = ({ chapters, onChapterSelect, selectedChapterId }) => {
    return (
        <div className="table-of-contents">
            <h2>目录</h2>
            <ul>
                {chapters.sort((a, b) => a.order - b.order).map(chapter => (
                    <li 
                        key={chapter.id} 
                        onClick={() => onChapterSelect(chapter)}
                        className={selectedChapterId === chapter.id ? 'active' : ''}
                    >
                        {chapter.title}
                    </li>
                ))}
            </ul>
        </div>
    );
};

export default TableOfContents;