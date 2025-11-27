import React from 'react';
import { XMarkIcon, SpeakerIcon } from './icons';

interface MediaModalProps {
    isOpen: boolean;
    onClose: () => void;
    src: string;
    type: 'image' | 'video' | 'audio' | null;
}

export const MediaModal: React.FC<MediaModalProps> = ({ isOpen, onClose, src, type }) => {
    if (!isOpen || !src) return null;

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-sm transition-opacity duration-300"
            onClick={onClose}
        >
            <button
                onClick={onClose}
                className="absolute top-4 right-4 p-2 text-white/70 hover:text-white bg-white/10 hover:bg-white/20 rounded-full transition-all z-50"
                aria-label="Close"
            >
                <XMarkIcon className="w-8 h-8" />
            </button>

            <div
                className="relative max-w-[95vw] max-h-[95vh] flex items-center justify-center p-2 outline-none"
                onClick={e => e.stopPropagation()}
            >
                {type === 'image' && (
                    <img
                        src={src}
                        alt="Full view"
                        className="max-w-full max-h-[90vh] object-contain rounded-lg shadow-2xl animate-in fade-in zoom-in duration-200"
                    />
                )}

                {type === 'video' && (
                    <video
                        src={src}
                        controls
                        autoPlay
                        className="max-w-full max-h-[90vh] rounded-lg shadow-2xl animate-in fade-in zoom-in duration-200"
                    />
                )}

                {type === 'audio' && (
                    <div className="bg-slate-800/90 backdrop-blur-xl p-10 rounded-2xl shadow-2xl border border-slate-700/50 w-[400px] flex flex-col items-center animate-in fade-in zoom-in duration-200">
                        <div className="w-32 h-32 bg-sky-500/20 rounded-full flex items-center justify-center mb-8 ring-4 ring-sky-500/10">
                            <SpeakerIcon className="w-16 h-16 text-sky-400" />
                        </div>
                        <audio src={src} controls autoPlay className="w-full" />
                    </div>
                )}
            </div>
        </div>
    );
};
