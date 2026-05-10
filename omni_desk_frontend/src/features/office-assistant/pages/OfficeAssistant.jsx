import { useState } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import MenuBar from '../components/MenuBar';
import '../components/OfficeAssistant.css';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faMagic, faLanguage, faSpellCheck } from '@fortawesome/free-solid-svg-icons';
import { processText } from '../api/officeAssistantApi';
import { toast } from 'react-toastify';
import { logger } from '../../../shared/utils/logger';


const OfficeAssistant = () => {
  const [isProcessing, setIsProcessing] = useState(false);
  const editor = useEditor({
    extensions: [
      StarterKit,
    ],
    content: `
      <h2>欢迎使用 Office 智能助手</h2>
      <p>在这里，您可以输入或粘贴文本，然后使用下方的AI工具进行智能纠错、翻译或润色。</p>
      <p>尝试一下吧！</p>
    `,
  });

  const handleAiAction = async (action) => {
    if (!editor) return;

    const text = editor.getHTML();
    setIsProcessing(true);
    toast.info(`正在进行 ${action}...`);

    try {
      const response = await processText(text, action);
      const processedText = response.data.processed_text;
      if (processedText) {
        editor.commands.setContent(processedText);
        toast.success(`${action} 完成！`);
      } else {
        toast.warn('AI未能返回有效内容。');
      }
    } catch (error) {
      logger.error(`Error during ${action}:`, error);
      toast.error(`处理失败: ${error.response?.data?.error || error.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="office-assistant-container">
      <h1>Office 智能助手</h1>
      <MenuBar editor={editor} />
      <EditorContent editor={editor} />
      <div className="ai-actions">
        <button onClick={() => handleAiAction('proofread')} disabled={isProcessing}>
          <FontAwesomeIcon icon={faSpellCheck} />
          {isProcessing ? '处理中...' : '智能纠错'}
        </button>
        <button onClick={() => handleAiAction('translate')} disabled={isProcessing}>
          <FontAwesomeIcon icon={faLanguage} />
          {isProcessing ? '处理中...' : '翻译'}
        </button>
        <button onClick={() => handleAiAction('polish')} disabled={isProcessing}>
          <FontAwesomeIcon icon={faMagic} />
          {isProcessing ? '处理中...' : '润色'}
        </button>
      </div>
    </div>
  );
};

export default OfficeAssistant;