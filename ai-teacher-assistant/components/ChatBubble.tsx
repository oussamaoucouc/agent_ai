import React from 'react';
import { Message, User } from '../types';
import { PlayIcon, StopIcon, UserIcon } from './icons';

interface ChatBubbleProps {
    message: Message;
    isPlaying: boolean;
    onPlayAudio: () => void;
    onStopAudio: () => void;
}

/**
 * Parses inline markdown elements like bold, italics, and links.
 * @param text The text content of a block element.
 * @returns An HTML string with inline elements formatted.
 */
const parseInlineMarkdown = (text: string): string => {
    let finalHtml = text;
    // Links: [text](url) - must be first to avoid conflicts with bold/italic markers
    finalHtml = finalHtml.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-sky-400 hover:text-sky-300 hover:underline">$1</a>');
    // Bold: **text**
    finalHtml = finalHtml.replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-gray-100">$1</strong>');
    // Italics: *text*
    finalHtml = finalHtml.replace(/\*(.*?)\*/g, '<em>$1</em>');
    return finalHtml;
}

/**
 * A more robust markdown parser that handles block-level elements first.
 * It processes headings, lists (ordered and unordered), and paragraphs.
 * @param text The raw text string from the agent.
 * @returns A formatted HTML string.
 */
const parseMarkdown = (text: string): string => {
    // Split the text into blocks separated by one or more empty lines.
    const blocks = text.split(/\n\s*\n/);

    const htmlBlocks = blocks.map(block => {
        const trimmedBlock = block.trim();
        if (!trimmedBlock) return '';

        // Headings
        if (trimmedBlock.startsWith('#')) {
            if (trimmedBlock.startsWith('###')) return `<h3 class="text-lg font-semibold my-2 text-gray-100">${parseInlineMarkdown(trimmedBlock.substring(4))}</h3>`;
            if (trimmedBlock.startsWith('##')) return `<h2 class="text-xl font-bold my-3 text-gray-50">${parseInlineMarkdown(trimmedBlock.substring(3))}</h2>`;
            if (trimmedBlock.startsWith('#')) return `<h1 class="text-2xl font-bold my-4 text-white">${parseInlineMarkdown(trimmedBlock.substring(2))}</h1>`;
        }

        // Lists
        const isUnorderedList = /^\s*[-*]/.test(trimmedBlock);
        const isOrderedList = /^\s*\d+\./.test(trimmedBlock);

        if (isUnorderedList || isOrderedList) {
            const lines = trimmedBlock.split('\n').filter(line => line.trim());
            if (lines.length === 0) return '';
            
            const listTag = isOrderedList ? 'ol' : 'ul';
            const listClass = isOrderedList ? 'list-decimal' : 'list-disc';
            
            const items = lines.map(line => {
                const itemContent = line.replace(/^\s*(?:-|\*|\d+\.)\s+/, '');
                // Skip lines that are just a list marker (e.g., "5.")
                if (!itemContent.trim()) return '';
                return `<li>${parseInlineMarkdown(itemContent)}</li>`;
            }).join('');

            return `<${listTag} class="${listClass} list-inside space-y-1.5 pl-2 my-2">${items}</${listTag}>`;
        }

        // Paragraphs (default)
        // Convert single newlines to <br> for line breaks within a paragraph.
        return `<p>${parseInlineMarkdown(trimmedBlock.replace(/\n/g, '<br />'))}</p>`;
    });

    // Join the processed blocks. A <p> block already has appropriate margins.
    return htmlBlocks.join('\n');
};


export const ChatBubble: React.FC<ChatBubbleProps> = ({ message, isPlaying, onPlayAudio, onStopAudio }) => {
    const isUser = message.sender === User.USER;

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
                <div className={`relative text-gray-300 p-4 rounded-xl ${isUser ? 'bg-sky-700 rounded-br-none' : 'bg-gray-800 rounded-tl-none'}`}>
                    <div 
                        className={`prose-p:m-0 prose-strong:text-white prose-em:text-gray-300 space-y-3 ${message.audioUrl && !isUser ? 'pr-10 pb-6' : ''}`}
                        dangerouslySetInnerHTML={{ __html: parseMarkdown(message.text) }} 
                    />
                    {message.audioUrl && !isUser && (
                        <div className="absolute bottom-3 right-3 z-10">
                            {isPlaying ? (
                                <button 
                                    onClick={onStopAudio} 
                                    title="Stop audio" 
                                    className="w-6 h-6 flex items-center justify-center rounded-full bg-red-600/80 hover:bg-red-600 text-white transition-all duration-200 transform hover:scale-110 focus:outline-none focus:ring-2 focus:ring-red-400 focus:ring-opacity-50"
                                >
                                    <StopIcon className="w-3 h-3" />
                                </button>
                            ) : (
                                <button 
                                    onClick={onPlayAudio} 
                                    title="Play audio" 
                                    className="w-6 h-6 flex items-center justify-center rounded-full bg-sky-600/80 hover:bg-sky-600 text-white transition-all duration-200 transform hover:scale-110 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-opacity-50"
                                >
                                    <PlayIcon className="w-3 h-3" />
                                </button>
                            )}
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
