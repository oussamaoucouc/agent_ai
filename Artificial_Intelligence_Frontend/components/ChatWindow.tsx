import React, { useEffect, useRef } from 'react';
import { ChatBubble } from './ChatBubble';
import { Message } from '../types';
import { AssistantIcon } from './icons';

interface ChatWindowProps {
    messages: Message[];
    isLoading: boolean;
    playingAudioId: string | null;
    streamingMessageId: string | null;  // ID of message currently being streamed
    onPlayAudio: (message: Message) => void;
    onStopAudio: () => void;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({ messages, isLoading, playingAudioId, streamingMessageId, onPlayAudio, onStopAudio }) => {
    const endOfMessagesRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isLoading]);

    return (
        <div className="flex-1 w-full overflow-y-auto px-4 space-y-8">
            {messages.map((msg) => (
                <ChatBubble
                    key={msg.id}
                    message={msg}
                    isPlaying={playingAudioId === msg.id}
                    isStreaming={streamingMessageId === msg.id}
                    onPlayAudio={() => onPlayAudio(msg)}
                    onStopAudio={onStopAudio}
                />
            ))}
            {isLoading && (
                <div className="flex items-start gap-3">
                    {/* Modern glowing avatar */}
                    <div className="relative flex-shrink-0 w-10 h-10">
                        <div className="absolute inset-0 rounded-full bg-gradient-to-r from-sky-400 via-teal-400 to-cyan-400 blur-md opacity-40 animate-pulse"></div>
                        <div className="absolute inset-0 rounded-full bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-600/50 flex items-center justify-center shadow-xl">
                            <AssistantIcon className="w-5 h-5 text-teal-300" />
                        </div>
                    </div>

                    <div className="flex flex-col gap-2 items-start">
                        <div className="font-semibold text-slate-200 flex items-center gap-2">
                            Assistant
                            <span className="text-xs font-normal text-sky-400/80 flex items-center gap-1">
                                <span className="relative flex h-2 w-2">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
                                    <span className="relative inline-flex rounded-full h-2 w-2 bg-sky-500"></span>
                                </span>
                                thinking
                            </span>
                        </div>

                        {/* Modern glassmorphic loading container */}
                        <div className="relative overflow-hidden w-fit bg-gradient-to-br from-slate-800/60 via-slate-800/40 to-slate-900/60 backdrop-blur-xl border border-slate-500/30 px-6 py-4 rounded-2xl rounded-tl-none shadow-2xl">
                            {/* Animated gradient border effect */}
                            <div className="absolute inset-0 rounded-2xl rounded-tl-none opacity-30">
                                <div className="absolute inset-0 bg-gradient-to-r from-sky-400/20 via-teal-400/20 to-cyan-400/20 animate-pulse"></div>
                            </div>

                            {/* Modern wave dots with staggered animation */}
                            <div className="relative flex items-center gap-1.5">
                                <div className="flex items-center gap-1.5">
                                    <div
                                        className="w-2.5 h-2.5 rounded-full bg-gradient-to-br from-sky-400 to-cyan-400 shadow-lg shadow-sky-400/50"
                                        style={{
                                            animation: 'modernBounce 1.4s ease-in-out infinite',
                                            animationDelay: '0s'
                                        }}
                                    ></div>
                                    <div
                                        className="w-2.5 h-2.5 rounded-full bg-gradient-to-br from-teal-400 to-emerald-400 shadow-lg shadow-teal-400/50"
                                        style={{
                                            animation: 'modernBounce 1.4s ease-in-out infinite',
                                            animationDelay: '0.2s'
                                        }}
                                    ></div>
                                    <div
                                        className="w-2.5 h-2.5 rounded-full bg-gradient-to-br from-cyan-400 to-sky-400 shadow-lg shadow-cyan-400/50"
                                        style={{
                                            animation: 'modernBounce 1.4s ease-in-out infinite',
                                            animationDelay: '0.4s'
                                        }}
                                    ></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
            <div ref={endOfMessagesRef} />
        </div>
    );
};