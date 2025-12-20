import React from 'react';
import { Tree } from 'antd';
import { useNavigate } from 'react-router-dom';

const { DirectoryTree } = Tree;

const TableOfContents = ({ books }) => {
    const navigate = useNavigate();

    const transformHeadingsToTree = (headings, bookId, chapterId) => {
        return headings.map(heading => ({
            title: heading.title,
            key: `heading-${bookId}-${chapterId}-${heading.id}`,
            children: heading.children ? transformHeadingsToTree(heading.children, bookId, chapterId) : [],
        }));
    };

    const transformBooksToTree = (booksData) => {
        return booksData.map(book => ({
            title: book.title,
            key: `book-${book.id}`,
            children: book.chapters.map(chapter => ({
                title: chapter.title,
                key: `chapter-${book.id}-${chapter.id}`,
                isLeaf: !chapter.heading_structure || chapter.heading_structure.length === 0,
                children: chapter.heading_structure ? transformHeadingsToTree(chapter.heading_structure, book.id, chapter.id) : [],
            })),
        }));
    };

    const treeData = transformBooksToTree(books);

    const onSelect = (keys, info) => {
        const [type, bookId, chapterId, ...rest] = info.node.key.split('-');
        
        if (type === 'chapter') {
            navigate(`/library/books/${bookId}/chapters/${chapterId}`);
        } else if (type === 'heading') {
            const headingId = rest.join('-');
            // Navigate to chapter and scroll to heading
            navigate(`/library/books/${bookId}/chapters/${chapterId}#${headingId}`);
        }
    };

    return (
        <DirectoryTree
            multiple
            defaultExpandAll
            onSelect={onSelect}
            treeData={treeData}
        />
    );
};

export default TableOfContents;