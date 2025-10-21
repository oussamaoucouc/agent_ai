import React, { useState } from 'react';
import { Message, User } from '../types';
import { PlayIcon, StopIcon, UserIcon, CopyIcon, CheckIcon } from './icons';

interface ChatBubbleProps {
    message: Message;
    isPlaying: boolean;
    onPlayAudio: () => void;
    onStopAudio: () => void;
}

const parseInlineMarkdown = (text: string): string => {
    let finalHtml = text;
    // Links
    finalHtml = finalHtml.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-sky-400 hover:text-sky-300 hover:underline">$1</a>');
    // Bold
    finalHtml = finalHtml.replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-gray-100">$1</strong>');
    // Italic
    finalHtml = finalHtml.replace(/\*(.*?)\*/g, '<em>$1</em>');
    return finalHtml;
};

const parseMarkdown = (text: string): string => {
    const lines = text.split('\n');
    let html = '';
    let currentBlock: string[] = [];
    let blockType: 'p' | 'ul' | 'ol' | null = null;

    const flushBlock = () => {
        if (currentBlock.length === 0) return;

        if (blockType === 'p') {
            html += `<p>${currentBlock.join('<br />')}</p>`;
        } else if (blockType === 'ul') {
            html += `<ul class="list-disc list-inside space-y-1.5 pl-2 my-2">${currentBlock.map(li => `<li>${li}</li>`).join('')}</ul>`;
        } else if (blockType === 'ol') {
            html += `<ol class="list-decimal list-inside space-y-1.5 pl-2 my-2">${currentBlock.map(li => `<li>${li}</li>`).join('')}</ol>`;
        }
        currentBlock = [];
        blockType = null;
    };

    for (const line of lines) {
        // H3 heading
        let match = line.match(/^###\s+(.*)/);
        if (match) {
            flushBlock();
            html += `<h3 class="text-lg font-semibold text-gray-100 mt-4 mb-2">${parseInlineMarkdown(match[1])}</h3>`;
            continue;
        }

        // Bold heading fallback
        match = line.match(/^\*\*(.+?):\*\*$/);
        if (match) {
            flushBlock();
            html += `<h3 class="text-lg font-semibold text-gray-100 mt-4 mb-2">${parseInlineMarkdown(match[1])}:</h3>`;
            continue;
        }
        
        // Unordered List
        match = line.match(/^\s*[-*]\s+(.*)/);
        if (match) {
            if (blockType !== 'ul') flushBlock();
            blockType = 'ul';
            currentBlock.push(parseInlineMarkdown(match[1]));
            continue;
        }

        // Ordered list
        match = line.match(/^\s*(\d+)\.\s+(.*)/);
        if (match) {
            if (blockType !== 'ol') flushBlock();
            blockType = 'ol';
            currentBlock.push(parseInlineMarkdown(match[2]));
            continue;
        }

        // Empty line
        if (line.trim() === '') {
            flushBlock();
            continue;
        }

        // Paragraph line
        if (blockType !== 'p') flushBlock();
        blockType = 'p';
        currentBlock.push(parseInlineMarkdown(line));
    }
    
    flushBlock();
    return html;
};


export const ChatBubble: React.FC<ChatBubbleProps> = ({ message, isPlaying, onPlayAudio, onStopAudio }) => {
    const isUser = message.sender === User.USER;
    const [showCopied, setShowCopied] = useState(false);

    const handleCopy = () => {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(message.text).then(() => {
                setShowCopied(true);
                setTimeout(() => setShowCopied(false), 2000);
            });
        }
    };

    return (
        <div className={`flex items-start gap-4 ${isUser ? 'justify-end' : ''}`}>
            {!isUser && (
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gradient-to-br from-teal-400 to-sky-600 flex items-center justify-center">
                    <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>
                </div>
            )}
            <div className={`grid gap-1.5 max-w-2xl ${isUser ? 'items-end' : ''}`}>
                <div className={`flex items-center gap-2 ${isUser ? 'justify-end' : ''}`}>
                    <div className="font-bold text-gray-200">{isUser ? 'You' : 'Assistant'}</div>
                </div>
                <div className={`relative text-gray-300 p-4 rounded-xl group ${isUser ? 'bg-sky-700 rounded-br-none' : 'bg-gray-800 rounded-tl-none'}`}>
                    <div 
                        className={`prose-p:m-0 prose-strong:text-white prose-em:text-gray-300 space-y-3 ${!isUser ? 'pb-8' : ''}`}
                        dangerouslySetInnerHTML={{ __html: parseMarkdown(message.text) }} 
                    />
                    {!isUser && (
                        <div className={`absolute bottom-2 right-2 z-10 flex items-center gap-1.5 bg-gray-900/50 backdrop-blur-sm p-1 rounded-lg transition-opacity duration-200 ${
                            isPlaying ? 'opacity-100' : 'opacity-0 group-hover:opacity-100 focus-within:opacity-100'
                        }`}>
                            {message.audioUrl && (
                                <>
                                    {isPlaying ? (
                                        <button 
                                            onClick={onStopAudio} 
                                            title="Stop audio" 
                                            className="p-1.5 flex items-center justify-center rounded-md bg-red-600/80 hover:bg-red-600 text-white transition-all"
                                        >
                                            <StopIcon className="w-4 h-4" />
                                        </button>
                                    ) : (
                                        <button 
                                            onClick={onPlayAudio} 
                                            title="Play audio" 
                                            className="p-1.5 flex items-center justify-center rounded-md text-gray-300 hover:bg-gray-700 hover:text-white transition-all"
                                        >
                                            <PlayIcon className="w-4 h-4" />
                                        </button>
                                    )}
                                </>
                            )}
                            <button onClick={handleCopy} title="Copy text" className="p-1.5 text-gray-300 hover:bg-gray-700 hover:text-white rounded-md transition-colors">
                                {showCopied ? <CheckIcon className="w-4 h-4 text-green-400" /> : <CopyIcon className="w-4 h-4" />}
                            </button>
                        </div>
                    )}
                </div>
            </div>
            {isUser && (
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gray-700 flex items-center justify-center">
                    <UserIcon className="w-6 h-6 text-gray-400" />
                </div>
            )}
        </div>
    );
};