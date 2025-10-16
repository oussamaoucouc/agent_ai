import React, { useEffect, useRef } from 'react';
import { ChatBubble } from './ChatBubble';
import { Message } from '../types';

interface ChatWindowProps {
    messages: Message[];
    isLoading: boolean;
    playingAudioId: string | null;
    onPlayAudio: (message: Message) => void;
    onStopAudio: () => void;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({ messages, isLoading, playingAudioId, onPlayAudio, onStopAudio }) => {
    const endOfMessagesRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isLoading]);

    return (
        <div className="flex-1 w-full overflow-y-auto pr-4 space-y-6">
            {messages.map((msg) => (
                <ChatBubble 
                    key={msg.id} 
                    message={msg}
                    isPlaying={playingAudioId === msg.id}
                    onPlayAudio={() => onPlayAudio(msg)}
                    onStopAudio={onStopAudio}
                />
            ))}
            {isLoading && (
                 <div className="flex items-start gap-4">
                    <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gradient-to-br from-teal-400 to-sky-600 flex items-center justify-center">
                        <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>
                    </div>
                    <div className="grid gap-1.5">
                        <div className="font-bold text-gray-200">Assistant</div>
                        <div className="text-gray-300 bg-gray-800 px-4 py-3 rounded-xl rounded-tl-none inline-block">
                            <div className="flex items-center justify-center space-x-2">
                                <div className="w-2 h-2 rounded-full bg-sky-400 animate-pulse"></div>
                                <div className="w-2 h-2 rounded-full bg-sky-400 animate-pulse [animation-delay:0.2s]"></div>
                                <div className="w-2 h-2 rounded-full bg-sky-400 animate-pulse [animation-delay:0.4s]"></div>
                            </div>
                        </div>
                    </div>
                 </div>
            )}
            <div ref={endOfMessagesRef} />
        </div>
    );
};