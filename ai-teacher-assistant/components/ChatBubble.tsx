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
 * A simple markdown parser to convert assistant responses into formatted HTML.
 * Handles paragraphs, bold, italics, and basic unordered/ordered lists.
 * @param text The raw text string.
 * @returns An HTML string.
 */
const parseMarkdown = (text: string): string => {
    // Split text into logical blocks based on double newlines
    const blocks = text.split(/\n\n+/);

    const htmlBlocks = blocks.map(block => {
        // Unordered list check
        if (/^(?:-|\*)\s/.test(block)) {
            const items = block.split('\n').map(item => `<li>${item.replace(/^(?:-|\*)\s/, '')}</li>`).join('');
            return `<ul class="list-disc list-inside space-y-1 my-2">${items}</ul>`;
        }
        // Ordered list check
        if (/^\d+\.\s/.test(block)) {
            const items = block.split('\n').map(item => `<li>${item.replace(/^\d+\.\s/, '')}</li>`).join('');
            return `<ol class="list-decimal list-inside space-y-1 my-2">${items}</ol>`;
        }
        // It's a paragraph
        return `<p>${block.replace(/\n/g, '<br />')}</p>`;
    });

    let finalHtml = htmlBlocks.join('');

    // Apply inline formatting (bold and italic) after block processing
    finalHtml = finalHtml
        .replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-gray-100">$1</strong>')
        .replace(/\*(.*?)\*/g, '<em class="italic">$1</em>');
        
    return finalHtml;
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
                        className={`prose-p:m-0 prose-strong:text-white prose-em:text-gray-300 ${message.audioUrl && !isUser ? 'pr-10 pb-6' : ''}`}
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