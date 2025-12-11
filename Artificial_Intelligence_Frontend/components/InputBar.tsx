import React, { useState, KeyboardEvent, useRef, useEffect } from 'react';
import { MicButton } from './MicButton';
import { SendIcon, ToolIcon, StopIcon, AgentIcon, DocumentWithTextIcon, PlusIcon, XMarkIcon, ImageIcon } from './icons';
import { QueryMode, MediaAttachment } from '../types';

interface InputBarProps {
    onSend: (text: string, mediaFiles?: MediaAttachment[]) => void;
    isRecording: boolean;
    onStartRecording: () => void;
    onStopRecording: () => void;
    isLoading: boolean;
    queryMode: QueryMode;
    onQueryModeChange: (mode: QueryMode) => void;
    onCancel: () => void;
    supportsImages?: boolean;
    supportsAudio?: boolean;
    supportsVideos?: boolean;
}

export const InputBar: React.FC<InputBarProps> = ({ onSend, isRecording, onStartRecording, onStopRecording, isLoading, queryMode, onQueryModeChange, onCancel, supportsImages, supportsAudio, supportsVideos }) => {
    const [text, setText] = useState('');
    const [mediaAttachments, setMediaAttachments] = useState<MediaAttachment[]>([]);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Auto-resize textarea height based on content
    useEffect(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = 'auto';
            const scrollHeight = textarea.scrollHeight;
            textarea.style.height = `${scrollHeight}px`;
        }
    }, [text]);

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;

        const newAttachments: MediaAttachment[] = [];
        Array.from(files).forEach((file: File) => {
            // Check file type based on capabilities
            let type: 'image' | 'audio' | 'video' | null = null;
            if (file.type.startsWith('image/') && supportsImages) type = 'image';
            else if (file.type.startsWith('audio/') && supportsAudio) type = 'audio';
            else if (file.type.startsWith('video/') && supportsVideos) type = 'video';

            if (type) {
                try {
                    const id = `${Date.now()}_${Math.random()}`;
                    const previewUrl = URL.createObjectURL(file);
                    const attachment: MediaAttachment = {
                        id,
                        file,
                        type,
                        previewUrl
                    };
                    newAttachments.push(attachment);
                } catch (err) {
                    console.error('Error creating preview for media:', err);
                }
            }
        });

        if (newAttachments.length > 0) {
            setMediaAttachments(prev => [...prev, ...newAttachments]);
        }
    };

    const removeAttachment = (id: string) => {
        setMediaAttachments(prev => {
            const attachment = prev.find(a => a.id === id);
            if (attachment?.previewUrl) {
                URL.revokeObjectURL(attachment.previewUrl);
            }
            return prev.filter(a => a.id !== id);
        });
    };

    const handleSend = () => {
        if (text.trim() || mediaAttachments.length > 0) {
            onSend(text, mediaAttachments.length > 0 ? mediaAttachments : undefined);
            setText('');
            setMediaAttachments([]);
            // Reset file input to allow re-selecting the same file
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
        }
    };

    const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            handleSend();
        }
    };

    const isMultimodal = supportsImages || supportsAudio || supportsVideos;
    const acceptedTypes = [
        supportsImages ? 'image/*' : '',
        supportsAudio ? 'audio/*' : '',
        supportsVideos ? 'video/*' : ''
    ].filter(Boolean).join(',');

    return (
        <div className="w-full space-y-2">
            {/* Media Preview */}
            {mediaAttachments.length > 0 && (
                <div className="flex flex-wrap gap-2 p-2 bg-slate-900/30 rounded-lg border border-slate-500/30">
                    {mediaAttachments.map(attachment => (
                        <div key={attachment.id} className="relative group">
                            <div className="w-20 h-20 rounded-lg overflow-hidden bg-slate-800 flex items-center justify-center border border-slate-700/50">
                                {attachment.previewUrl ? (
                                    attachment.type === 'image' || attachment.type === 'video' ? (
                                        <img src={attachment.previewUrl} alt="Preview" className="w-full h-full object-cover" />
                                    ) : (
                                        <div className="text-xs text-slate-400 p-1 text-center">{attachment.file.name}</div>
                                    )
                                ) : (
                                    <ImageIcon className="w-8 h-8 text-slate-500" />
                                )}
                            </div>
                            <button
                                onClick={() => removeAttachment(attachment.id)}
                                className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-red-600 hover:bg-red-700 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                                <XMarkIcon className="w-3 h-3 text-white" />
                            </button>
                            <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-[10px] px-1 truncate">
                                {attachment.file.name}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Input Bar */}
            <div className="w-full bg-slate-900/30 p-3 rounded-xl border border-slate-500/30 flex items-center gap-3 shadow-lg backdrop-blur-lg">
                {/* Plus Button for Media Upload - Only if Multimodal and Agent Mode - LEFT SIDE */}
                {!isLoading && isMultimodal && queryMode === 'agent' && (
                    <div className="relative group">
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept={acceptedTypes}
                            multiple
                            onChange={handleFileSelect}
                            className="hidden"
                        />
                        <button
                            onClick={() => fileInputRef.current?.click()}
                            disabled={isLoading || isRecording}
                            className="p-2.5 rounded-full bg-gradient-to-br from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 shadow-lg shadow-indigo-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 transform hover:scale-105 active:scale-95"
                            aria-label="Attach media"
                        >
                            <PlusIcon className="w-5 h-5 text-white" />
                        </button>
                        <span className="absolute -bottom-8 whitespace-nowrap text-xs text-white bg-gray-900/90 backdrop-blur-md px-2.5 py-1.5 rounded-lg border border-white/10 opacity-0 group-hover:opacity-100 transition-all duration-200 pointer-events-none translate-y-1 group-hover:translate-y-0 z-50">
                            Multimodel Capabilities
                        </span>
                    </div>
                )}

                <textarea
                    ref={textareaRef}
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Type your question here or use the microphone..."
                    className="flex-1 bg-transparent resize-none text-slate-200 placeholder-slate-500 focus:outline-none max-h-32 overflow-y-auto"
                    rows={1}
                    disabled={isLoading || isRecording}
                />
                <div className="flex items-center gap-2">
                    {isLoading ? (
                        <div className="relative group flex flex-col items-center">
                            <button
                                onClick={onCancel}
                                className="p-2.5 rounded-full bg-red-600 hover:bg-red-500 transition-colors"
                                aria-label="Cancel generation"
                            >
                                <StopIcon className="w-5 h-5 text-white" />
                            </button>
                            <span className="absolute -bottom-8 whitespace-nowrap text-xs text-white bg-gray-900/80 backdrop-blur-sm px-2 py-1 rounded-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                                Cancel
                            </span>
                        </div>
                    ) : (
                        <>
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

                            <div className="bg-slate-800/40 border border-slate-600/50 p-0.5 rounded-full flex items-center gap-0.5">
                                <div className="relative group flex flex-col items-center">
                                    <button
                                        onClick={() => onQueryModeChange('agent')}
                                        disabled={isLoading || isRecording}
                                        className={`p-2 rounded-full ${queryMode === 'agent' ? 'bg-sky-600 hover:bg-sky-500' : 'bg-transparent hover:bg-white/10'} disabled:bg-slate-700 disabled:cursor-not-allowed transition-colors`}
                                        aria-label="Assistant Agent Mode"
                                        aria-pressed={queryMode === 'agent'}
                                    >
                                        <AgentIcon className="w-5 h-5 text-white" />
                                    </button>
                                    <span className="absolute -bottom-8 whitespace-nowrap text-xs text-white bg-gray-900/80 backdrop-blur-sm px-2 py-1 rounded-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                                        Assistant Agent
                                    </span>
                                </div>
                                <div className="relative group flex flex-col items-center">
                                    <button
                                        onClick={() => onQueryModeChange('direct')}
                                        disabled={isLoading || isRecording}
                                        className={`p-2 rounded-full ${queryMode === 'direct' ? 'bg-sky-600 hover:bg-sky-500' : 'bg-transparent hover:bg-white/10'} disabled:bg-slate-700 disabled:cursor-not-allowed transition-colors`}
                                        aria-label="Document Search Mode"
                                        aria-pressed={queryMode === 'direct'}
                                    >
                                        <DocumentWithTextIcon className="w-5 h-5 text-white" />
                                    </button>
                                    <span className="absolute -bottom-8 whitespace-nowrap text-xs text-white bg-gray-900/80 backdrop-blur-sm px-2 py-1 rounded-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                                        Document Search
                                    </span>
                                </div>
                                <div className="relative group flex flex-col items-center">
                                    <button
                                        onClick={() => onQueryModeChange('tools')}
                                        disabled={isLoading || isRecording}
                                        className={`p-2 rounded-full ${queryMode === 'tools' ? 'bg-sky-600 hover:bg-sky-500' : 'bg-transparent hover:bg-white/10'} disabled:bg-slate-700 disabled:cursor-not-allowed transition-colors`}
                                        aria-label="Tools Mode"
                                        aria-pressed={queryMode === 'tools'}
                                    >
                                        <ToolIcon className="w-5 h-5 text-white" />
                                    </button>
                                    <span className="absolute -bottom-8 whitespace-nowrap text-xs text-white bg-gray-900/80 backdrop-blur-sm px-2 py-1 rounded-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                                        Tools
                                    </span>
                                </div>
                            </div>

                            <div className="relative group flex flex-col items-center">
                                <button
                                    onClick={handleSend}
                                    disabled={isLoading || isRecording || (!text.trim() && mediaAttachments.length === 0)}
                                    className="p-2.5 rounded-full bg-sky-600 hover:bg-sky-500 disabled:bg-slate-700 disabled:cursor-not-allowed transition-colors"
                                    aria-label="Send message"
                                >
                                    <SendIcon className="w-5 h-5 text-white" />
                                </button>
                                <span className="absolute -bottom-8 whitespace-nowrap text-xs text-white bg-gray-900/80 backdrop-blur-sm px-2 py-1 rounded-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                                    Send
                                </span>
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
};
