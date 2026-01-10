import React, { useState, useRef, useEffect } from 'react';
import { TTSVoice } from '../types';
import { SpeakerIcon, CheckIcon } from './icons';

interface VoiceSelectorProps {
    currentVoice: TTSVoice;
    onVoiceChange: (voice: TTSVoice) => void;
    availableVoices: { label: string; id: string }[];
}

const ChevronDownIcon = ({ className }: { className?: string }) => (
    <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
    >
        <polyline points="6 9 12 15 18 9" />
    </svg>
);

/**
 * Collapsible voice selector component.
 * Shows current voice in collapsed state, expands to show all available voices.
 */
export const VoiceSelector: React.FC<VoiceSelectorProps> = ({
    currentVoice,
    onVoiceChange,
    availableVoices,
}) => {
    const [isOpen, setIsOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    // Get current voice label
    const currentVoiceLabel = availableVoices.find(v => v.id === currentVoice)?.label || currentVoice;

    // Close on outside click
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };

        if (isOpen) {
            document.addEventListener('mousedown', handleClickOutside);
        }
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [isOpen]);

    // Close on Escape key
    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape' && isOpen) {
                setIsOpen(false);
            }
        };

        document.addEventListener('keydown', handleKeyDown);
        return () => {
            document.removeEventListener('keydown', handleKeyDown);
        };
    }, [isOpen]);

    const handleVoiceSelect = (voiceId: string) => {
        onVoiceChange(voiceId as TTSVoice);
        setIsOpen(false);
    };

    if (!availableVoices || availableVoices.length === 0) {
        return (
            <div className="text-xs text-slate-500">No voices configured.</div>
        );
    }

    return (
        <div ref={containerRef} className="relative">
            {/* Header / Trigger Button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className={`
                    w-full flex items-center justify-between
                    bg-slate-800/50 backdrop-blur-sm
                    border border-slate-600/50
                    text-slate-200 text-xs
                    rounded-lg px-3 py-2
                    hover:bg-slate-700/50 hover:border-slate-500
                    focus:outline-none focus:ring-2 focus:ring-sky-500/50
                    transition-all duration-200 ease-in-out
                    ${isOpen ? 'ring-2 ring-sky-500/50 border-sky-500' : ''}
                `}
            >
                <div className="flex items-center gap-1.5">
                    <SpeakerIcon className="w-3.5 h-3.5 text-slate-400" />
                    <span className="font-medium">Voice:</span>
                    <span className="text-sky-400 font-semibold">{currentVoiceLabel}</span>
                </div>
                <ChevronDownIcon
                    className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
                />
            </button>

            {/* Dropdown Panel */}
            <div
                className={`
                    absolute z-50 w-full mt-2
                    bg-slate-900/95 backdrop-blur-xl
                    border border-slate-700/50
                    rounded-lg shadow-xl shadow-black/50
                    overflow-hidden
                    transition-all duration-200 ease-out origin-top
                    ${isOpen
                        ? 'opacity-100 scale-100 translate-y-0'
                        : 'opacity-0 scale-95 -translate-y-2 pointer-events-none'}
                `}
            >
                <div className="max-h-60 overflow-y-auto py-1 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                    {availableVoices.map((voice) => {
                        const isSelected = currentVoice === voice.id;
                        return (
                            <button
                                key={voice.id}
                                onClick={() => handleVoiceSelect(voice.id)}
                                className={`
                                    w-full text-left px-3 py-2 text-sm
                                    transition-colors duration-150
                                    flex items-center justify-between
                                    ${isSelected
                                        ? 'bg-sky-600/20 text-sky-400'
                                        : 'text-slate-300 hover:bg-slate-800 hover:text-white'}
                                `}
                            >
                                <span className="font-medium">{voice.label}</span>
                                {isSelected && (
                                    <CheckIcon className="w-4 h-4 text-sky-400" />
                                )}
                            </button>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};
