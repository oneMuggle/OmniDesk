import React, { useState } from 'react';
import PropTypes from 'prop-types';
import api from '../api/axiosConfig';
import './AnnotationHandler.css';

const AnnotationHandler = ({ chapterId, children }) => {
    const [selection, setSelection] = useState(null);
    const [note, setNote] = useState('');

    const handleMouseUp = () => {
        const currentSelection = window.getSelection();
        if (currentSelection.rangeCount > 0) {
            const range = currentSelection.getRangeAt(0);
            if (!range.collapsed) {
                setSelection(range);
            }
        }
    };

    const handleSaveAnnotation = async () => {
        if (!selection) return;

        try {
            await api.post(`/api/documents/chapters/${chapterId}/add_annotation/`, {
                selected_text: selection.toString(),
                note: note,
            });
            // Optionally, highlight the text permanently after saving
            highlightSelection(selection, note);
            setSelection(null);
            setNote('');
        } catch (error) {
            console.error('Failed to save annotation:', error);
        }
    };

    const highlightSelection = (range, noteText) => {
        const span = document.createElement('span');
        span.className = 'highlighted-text';
        span.title = noteText;
        range.surroundContents(span);
    };

    return (
        <div onMouseUp={handleMouseUp}>
            {children}
            {selection && (
                <div className="annotation-popup">
                    <textarea
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        placeholder="添加批注..."
                    />
                    <button onClick={handleSaveAnnotation}>保存批注</button>
                    <button onClick={() => setSelection(null)}>取消</button>
                </div>
            )}
        </div>
    );
};

AnnotationHandler.propTypes = {
  chapterId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  children: PropTypes.node.isRequired,
};

export default AnnotationHandler;