
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
            <h2 className="mt-8 text-2xl font-bold text-gray-200">AI Teacher Assistant</h2>
             {isLoading ? (
                <p className="mt-2 text-sky-300 max-w-sm">Thinking...</p>
             ) : isSpeaking ? (
                <p className="mt-2 text-gray-400 max-w-sm">Listening...</p>
            ) : isConversationStarted ? (
                <p className="mt-2 text-gray-400 max-w-md">
                    What would you like to explore next? Feel free to ask another question.
                </p>
            ) : (
                <>
                    <p className="mt-2 text-gray-400 max-w-md text-lg">
                        I'm ready to help you learn!
                    </p>
                    <p className="mt-1 text-gray-400 max-w-md">
                        What topic should we explore today? Use the microphone or type your question below.
                    </p>
                </>
            )}
        </div>
    );
};
