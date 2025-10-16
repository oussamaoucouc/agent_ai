
import React from 'react';
import { MicIcon, StopIcon } from './icons';

interface MicButtonProps {
    isRecording: boolean;
    onStart: () => void;
    onStop: () => void;
    disabled: boolean;
}

export const MicButton: React.FC<MicButtonProps> = ({ isRecording, onStart, onStop, disabled }) => {
    const handleClick = () => {
        if (isRecording) {
            onStop();
        } else {
            onStart();
        }
    };

    return (
        <button
            onClick={handleClick}
            disabled={disabled}
            className={`p-2 rounded-full transition-colors ${
                isRecording
                    ? 'bg-red-600 hover:bg-red-500 animate-pulse'
                    : 'bg-gray-700 hover:bg-gray-600'
            } disabled:bg-gray-600 disabled:cursor-not-allowed`}
            aria-label={isRecording ? 'Stop recording' : 'Start recording'}
        >
            {isRecording ? <StopIcon className="w-5 h-5 text-white" /> : <MicIcon className="w-5 h-5 text-white" />}
        </button>
    );
};
