import React from 'react';
import PropTypes from 'prop-types';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faBold, faItalic, faStrikethrough, faParagraph,
  faListUl, faListOl, faQuoteRight, faUndo, faRedo
} from '@fortawesome/free-solid-svg-icons';

const MenuBar = ({ editor }) => {
  if (!editor) {
    return null;
  }

  const menuItems = [
    { action: () => editor.chain().focus().toggleBold().run(), icon: faBold, title: 'Bold', isActive: editor.isActive('bold') },
    { action: () => editor.chain().focus().toggleItalic().run(), icon: faItalic, title: 'Italic', isActive: editor.isActive('italic') },
    { action: () => editor.chain().focus().toggleStrike().run(), icon: faStrikethrough, title: 'Strike', isActive: editor.isActive('strike') },
    { action: () => editor.chain().focus().setParagraph().run(), icon: faParagraph, title: 'Paragraph', isActive: editor.isActive('paragraph') },
    { action: () => editor.chain().focus().toggleHeading({ level: 1 }).run(), title: 'H1', content: 'H1', isActive: editor.isActive('heading', { level: 1 }) },
    { action: () => editor.chain().focus().toggleHeading({ level: 2 }).run(), title: 'H2', content: 'H2', isActive: editor.isActive('heading', { level: 2 }) },
    { action: () => editor.chain().focus().toggleHeading({ level: 3 }).run(), title: 'H3', content: 'H3', isActive: editor.isActive('heading', { level: 3 }) },
    { action: () => editor.chain().focus().toggleBulletList().run(), icon: faListUl, title: 'Bullet List', isActive: editor.isActive('bulletList') },
    { action: () => editor.chain().focus().toggleOrderedList().run(), icon: faListOl, title: 'Ordered List', isActive: editor.isActive('orderedList') },
    { action: () => editor.chain().focus().toggleBlockquote().run(), icon: faQuoteRight, title: 'Blockquote', isActive: editor.isActive('blockquote') },
    { action: () => editor.chain().focus().undo().run(), icon: faUndo, title: 'Undo' },
    { action: () => editor.chain().focus().redo().run(), icon: faRedo, title: 'Redo' },
  ];

  return (
    <div className="editor-menu-bar">
      {menuItems.map((item, index) => (
        <button
          key={index}
          onClick={item.action}
          className={item.isActive ? 'is-active' : ''}
          title={item.title}
        >
          {item.icon ? <FontAwesomeIcon icon={item.icon} /> : item.content}
        </button>
      ))}
    </div>
  );
};

MenuBar.propTypes = {
  editor: PropTypes.object,
};

MenuBar.defaultProps = {
  editor: null,
};

export default MenuBar;