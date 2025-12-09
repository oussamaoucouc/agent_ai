import React from 'react';
import { Avatar } from './Avatar';

interface AvatarViewProps {
    isSpeaking: boolean;
    isLoading: boolean;
    currentViseme: string;
    isConversationStarted: boolean;
}

export const AvatarView: React.FC<AvatarViewProps> = ({ isSpeaking, isLoading, currentViseme, isConversationStarted }) => {
    return (
        <div className="flex flex-col items-center justify-center p-8 text-center">
            <Avatar isSpeaking={isSpeaking} currentViseme={currentViseme} isLoading={isLoading} />
            <h2 className="mt-8 text-2xl font-bold text-slate-200">AI Assistant</h2>
            {isLoading ? (
                <p className="mt-2 text-sky-300 max-w-sm">Generating Speaking...</p>
            ) : isSpeaking ? (
                <div className="flex items-center justify-center gap-2 mt-2">
                    <div className="flex gap-0.5">
                        <span className="w-1 h-3 bg-cyan-400 rounded-full animate-pulse" style={{ animationDelay: '0s' }}></span>
                        <span className="w-1 h-4 bg-teal-400 rounded-full animate-pulse" style={{ animationDelay: '0.15s' }}></span>
                        <span className="w-1 h-3 bg-cyan-400 rounded-full animate-pulse" style={{ animationDelay: '0.3s' }}></span>
                    </div>
                    <p className="text-slate-400 max-w-sm">Speaking...</p>
                </div>
            ) : isConversationStarted ? (
                <p className="mt-2 text-slate-400 max-w-md">
                    What would you like to explore next? Feel free to ask another question.
                </p>
            ) : (
                <>
                    <p className="mt-2 text-slate-400 max-w-md text-lg">
                        I'm ready to help!
                    </p>
                    <p className="mt-1 text-slate-400 max-w-md">
                        How can I assist you today? Use the microphone or type your question below.
                    </p>
                </>
            )}
        </div>
    );
};