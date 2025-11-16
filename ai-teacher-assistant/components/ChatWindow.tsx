import React, { useEffect, useRef } from 'react';
import { ChatBubble } from './ChatBubble';
import { Message } from '../types';
import { AssistantIcon } from './icons';

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
        <div className="flex-1 w-full overflow-y-auto pr-4 space-y-8">
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
                 <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-700/60 flex items-center justify-center shadow-md">
                        <AssistantIcon className="w-5 h-5 text-teal-300" />
                    </div>
                    <div className="grid gap-1.5">
                         <div className="font-bold text-slate-200">Assistant</div>
                        <div className="bg-slate-800/40 backdrop-blur-sm border border-slate-600/50 px-4 py-3 rounded-2xl rounded-tl-none inline-block">
                            <div className="flex items-center justify-center space-x-2">
                                <div className="w-2 h-2 rounded-full bg-sky-400 animate-pulse [animation-delay:-0.3s]"></div>
                                <div className="w-2 h-2 rounded-full bg-sky-400 animate-pulse [animation-delay:-0.15s]"></div>
                                <div className="w-2 h-2 rounded-full bg-sky-400 animate-pulse"></div>
                            </div>
                        </div>
                    </div>
                 </div>
            )}
            <div ref={endOfMessagesRef} />
        </div>
    );
};