import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';

/**
 * 替代 react-quill 的富文本编辑器(基于 tiptap)。
 *
 * API 设计:与原 ReactQuill 保持基本一致,
 * - value: HTML 字符串(受控)
 * - onChange: (html: string) => void
 * - placeholder / className / style 等基础属性
 *
 * 行为差异(已知):
 * - 工具栏使用 tiptap 默认 UI(无 quill.snow.css 主题)。
 * - 输出仍是 HTML 字符串,后端无需改动。
 */
const RichTextEditor = ({
    value = '',
    onChange,
    placeholder = '请输入内容...',
    className,
    style,
}) => {
    const editor = useEditor({
        extensions: [StarterKit],
        content: value,
        editorProps: {
            attributes: {
                'data-placeholder': placeholder,
            },
        },
        onUpdate: ({ editor: currentEditor }) => {
            onChange?.(currentEditor.getHTML());
        },
    });

    return (
        <div className={className} style={style}>
            <EditorContent editor={editor} />
        </div>
    );
};

export default RichTextEditor;
