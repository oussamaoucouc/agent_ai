import React, { useState, KeyboardEvent, useRef, useEffect } from 'react';
import { MicButton } from './MicButton';
import { SendIcon, ToolIcon } from './icons';

interface InputBarProps {
    onSend: (text: string) => void;
    isRecording: boolean;
    onStartRecording: () => void;
    onStopRecording: () => void;
    isLoading: boolean;
    isToolsActive: boolean;
    onToggleTools: () => void;
}

export const InputBar: React.FC<InputBarProps> = ({ onSend, isRecording, onStartRecording, onStopRecording, isLoading, isToolsActive, onToggleTools }) => {
    const [text, setText] = useState('');
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Auto-resize textarea height based on content
    useEffect(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = 'auto'; // Reset height to recalculate
            const scrollHeight = textarea.scrollHeight;
            textarea.style.height = `${scrollHeight}px`; // Set height to content height
        }
    }, [text]); // Run this effect whenever text changes

    const handleSend = () => {
        if (text.trim()) {
            onSend(text);
            setText('');
        }
    };

    const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            handleSend();
        }
    };

    return (
        <div className="w-full bg-gray-800/50 p-3 rounded-xl border border-gray-700 flex items-end gap-3 shadow-lg">
            <textarea
                ref={textareaRef}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type your question here or use the microphone..."
                className="flex-1 bg-transparent resize-none text-gray-200 placeholder-gray-500 focus:outline-none max-h-32 overflow-y-auto"
                rows={1}
                disabled={isLoading || isRecording}
            />
            <div className="flex items-end gap-3">
                <div className="relative group flex flex-col items-center">
                    <MicButton
                        isRecording={isRecording}
                        onStart={onStartRecording}
                        onStop={onStopRecording}
                        disabled={isLoading}
                    />
                    <span className="absolute -bottom-8 whitespace-nowrap text-xs text-white bg-gray-900/80 backdrop-blur-sm px-2 py-1 rounded-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                        Mic
                    </span>
                </div>
                <div className="relative group flex flex-col items-center">
                    <button
                        onClick={onToggleTools}
                        disabled={isLoading || isRecording}
                        className={`p-2 rounded-full ${isToolsActive ? 'bg-sky-600 hover:bg-sky-500' : 'bg-gray-700 hover:bg-gray-600'} disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors`}
                        aria-label="Tools"
                        aria-pressed={isToolsActive}
                    >
                        <ToolIcon className="w-5 h-5 text-white" />
                    </button>
                    <span className="absolute -bottom-8 whitespace-nowrap text-xs text-white bg-gray-900/80 backdrop-blur-sm px-2 py-1 rounded-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                        Tools
                    </span>
                </div>
                <div className="relative group flex flex-col items-center">
                    <button
                        onClick={handleSend}
                        disabled={isLoading || isRecording || !text.trim()}
                        className="p-2 rounded-full bg-sky-600 hover:bg-sky-500 disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors"
                        aria-label="Send message"
                    >
                        <SendIcon className="w-5 h-5 text-white" />
                    </button>
                    <span className="absolute -bottom-8 whitespace-nowrap text-xs text-white bg-gray-900/80 backdrop-blur-sm px-2 py-1 rounded-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                        Send
                    </span>
                </div>
            </div>
        </div>
    );
};