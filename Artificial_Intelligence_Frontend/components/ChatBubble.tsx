import React, { useState } from 'react';
import { Message, User } from '../types';
import { PlayIcon, StopIcon, UserIcon, CopyIcon, CheckIcon, AssistantIcon, MaximizeIcon } from './icons';
import { MediaModal } from './MediaModal';

interface ChatBubbleProps {
    message: Message;
    isPlaying: boolean;
    onPlayAudio: () => void;
    onStopAudio: () => void;
}

const parseInlineMarkdown = (text: string): string => {
    let finalHtml = text;
    // Inline code with backticks
    finalHtml = finalHtml.replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 bg-slate-700/50 text-sky-300 rounded text-sm font-mono">$1</code>');
    // Links
    finalHtml = finalHtml.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-sky-400 hover:text-sky-300 hover:underline">$1</a>');
    // Bold
    finalHtml = finalHtml.replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-slate-100">$1</strong>');
    // Italic
    finalHtml = finalHtml.replace(/\*(.*?)\*/g, '<em>$1</em>');
    return finalHtml;
};

const parseMarkdown = (text: string): string => {
    // Clean up any JSON-like formatting that might have slipped through
    let cleanText = text
        .replace(/^\s*\{\s*$/gm, '') // Remove opening braces
        .replace(/^\s*\}\s*$/gm, '') // Remove closing braces
        .replace(/^\s*"[^"]*":\s*\[\s*$/gm, '') // Remove JSON array starts
        .replace(/^\s*"[^"]*":\s*"([^"]*)"[,]?\s*$/gm, '$1') // Extract quoted values
        .replace(/^\s*\]\s*[,]?\s*$/gm, '') // Remove array endings
        .replace(/^\s*[,]\s*$/gm, '') // Remove stray commas
        .trim();

    const lines = cleanText.split('\n');
    let html = '';
    let currentBlock: string[] = [];
    let blockType: 'p' | 'ul' | 'ol' | 'table' | null = null;
    let tableRows: string[] = [];
    let isTableHeader = true;

    const flushBlock = () => {
        if (currentBlock.length === 0 && tableRows.length === 0) return;

        if (blockType === 'p') {
            html += `<div class="mb-3 leading-relaxed">${currentBlock.join('<br />')}</div>`;
        } else if (blockType === 'ul') {
            html += `<ul class="list-disc list-inside space-y-2 pl-4 my-3 text-slate-200">${currentBlock.map(li => `<li class="leading-relaxed">${li}</li>`).join('')}</ul>`;
        } else if (blockType === 'ol') {
            html += `<ol class="list-decimal list-inside space-y-2 pl-4 my-3 text-slate-200">${currentBlock.map(li => `<li class="leading-relaxed">${li}</li>`).join('')}</ol>`;
        } else if (blockType === 'table' && tableRows.length > 0) {
            html += `<div class="overflow-x-auto my-4">
                <table class="min-w-full border-collapse border border-slate-600/50 bg-slate-800/20 rounded-lg">
                    ${tableRows.join('')}
                </table>
            </div>`;
            tableRows = [];
            isTableHeader = true;
        }
        currentBlock = [];
        blockType = null;
    };

    const parseTableRow = (line: string, isHeader: boolean = false): string => {
        const cells = line.split('|').map(cell => cell.trim()).filter(cell => cell !== '');
        const tag = isHeader ? 'th' : 'td';
        const cellClass = isHeader
            ? 'px-4 py-3 text-left font-semibold text-white bg-white/10 border border-slate-600/50'
            : 'px-4 py-3 text-slate-200 border border-slate-600/50';

        return `<tr class="${isHeader ? '' : 'hover:bg-white/5'}">
            ${cells.map(cell => `<${tag} class="${cellClass}">${parseInlineMarkdown(cell)}</${tag}>`).join('')}
        </tr>`;
    };

    for (const line of lines) {
        // Skip empty or whitespace-only lines
        if (line.trim() === '') {
            flushBlock();
            continue;
        }

        // Horizontal rule (---) - convert to styled divider
        if (/^-{3,}$/.test(line.trim())) {
            flushBlock();
            html += `<hr class="my-4 border-t border-slate-600/30" />`;
            continue;
        }

        // H1 heading (#) - largest heading
        let match = line.match(/^#\s+(.*)$/);
        if (match) {
            flushBlock();
            const title = parseInlineMarkdown(match[1]);
            html += `<h1 class="text-2xl font-bold text-white mt-4 mb-3 first:mt-0">${title}</h1>`;
            continue;
        }

        // H2 heading (##) - second-level heading
        match = line.match(/^##\s+(.*)$/);
        if (match) {
            flushBlock();
            const title = parseInlineMarkdown(match[1]);
            html += `<h2 class="text-xl font-bold text-white mt-4 mb-2 first:mt-0">${title}</h2>`;
            continue;
        }

        // H3 heading with enhanced styling
        match = line.match(/^###\s+(.*)/);
        if (match) {
            flushBlock();
            const title = parseInlineMarkdown(match[1].replace(/^\[|\]$/g, '')); // Remove brackets if present
            html += `<h3 class="text-xl font-bold text-white mt-6 mb-3 pb-2 border-b border-slate-500/30 first:mt-0">${title}</h3>`;
            continue;
        }

        // H4 heading (#### ) - for numbered tool sections
        match = line.match(/^####\s+(.*)/);
        if (match) {
            flushBlock();
            const title = parseInlineMarkdown(match[1].replace(/^`|`$/g, '')); // Remove surrounding backticks if present
            html += `<h4 class="text-lg font-semibold text-sky-300 mt-5 mb-2 first:mt-0">${title}</h4>`;
            continue;
        }

        // Bold heading fallback with better styling
        match = line.match(/^\*\*(.+?):\*\*$/);
        if (match) {
            flushBlock();
            html += `<h4 class="text-lg font-semibold text-slate-100 mt-4 mb-2">${parseInlineMarkdown(match[1])}:</h4>`;
            continue;
        }

        // Enhanced bold inline patterns (Source:, Context:, etc.)
        match = line.match(/^\*\*([^:]+):\*\*\s*(.*)/);
        if (match) {
            flushBlock();
            html += `<div class="mb-2"><span class="font-semibold text-sky-300">${match[1]}:</span> <span class="text-slate-200">${parseInlineMarkdown(match[2])}</span></div>`;
            continue;
        }

        // Unordered List with better spacing
        match = line.match(/^\s*[-*]\s+(.*)/);
        if (match) {
            if (blockType !== 'ul') flushBlock();
            blockType = 'ul';
            currentBlock.push(parseInlineMarkdown(match[1]));
            continue;
        }

        // Ordered list
        match = line.match(/^\s*(\d+)\.\s+(.*)/);
        if (match) {
            if (blockType !== 'ol') flushBlock();
            blockType = 'ol';
            currentBlock.push(parseInlineMarkdown(match[2]));
            continue;
        }

        // Code block handling - Ignore fences for now to prevent artifacts around tables
        if (/^\s*```/.test(line)) {
            continue;
        }

        // Table detection - check for pipe-separated values
        if (line.includes('|') && line.trim().split('|').length >= 3) {
            // Check if it's a separator line (like |---|---|)
            const isSeparator = /^\s*\|[\s\-:]*\|[\s\-:|]*$/.test(line);

            if (!isSeparator) {
                if (blockType !== 'table') {
                    flushBlock();
                    blockType = 'table';
                    isTableHeader = true;
                }

                tableRows.push(parseTableRow(line, isTableHeader));
                isTableHeader = false;
                continue;
            } else {
                // Skip separator lines but continue table processing
                continue;
            }
        } else if (blockType === 'table') {
            // End of table, flush it
            flushBlock();
        }

        // Paragraph line
        if (blockType !== 'p') flushBlock();
        blockType = 'p';
        currentBlock.push(parseInlineMarkdown(line));
    }

    flushBlock();
    return html;
};


export const ChatBubble: React.FC<ChatBubbleProps> = ({ message, isPlaying, onPlayAudio, onStopAudio }) => {
    const isUser = message.sender === User.USER;
    const [showCopied, setShowCopied] = useState(false);
    const [mediaModalOpen, setMediaModalOpen] = useState(false);
    const [selectedMedia, setSelectedMedia] = useState<{ src: string, type: 'image' | 'video' | 'audio' } | null>(null);

    const openMedia = (src: string, type: 'image' | 'video' | 'audio') => {
        setSelectedMedia({ src, type });
        setMediaModalOpen(true);
    };

    const closeMedia = () => {
        setMediaModalOpen(false);
        setSelectedMedia(null);
    };

    const handleCopy = () => {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(message.text).then(() => {
                setShowCopied(true);
                setTimeout(() => setShowCopied(false), 2000);
            });
        }
    };

    return (
        <div className={`flex items-start gap-3 ${isUser ? 'justify-end' : ''}`}>
            {!isUser && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-700/60 flex items-center justify-center shadow-md">
                    <AssistantIcon className="w-5 h-5 text-teal-300" />
                </div>
            )}
            <div className={`flex flex-col gap-1.5 max-w-2xl ${isUser ? 'items-end' : 'items-start'}`}>
                <div className="font-bold text-slate-200">{isUser ? 'You' : 'Assistant'}</div>
                <div className={`relative text-slate-200 p-4 group ${isUser ? 'bg-gradient-to-br from-indigo-500/30 via-blue-500/20 to-sky-500/20 backdrop-blur-xl border border-white/10 shadow-lg shadow-blue-500/10 rounded-2xl rounded-br-sm' : 'bg-slate-800/40 backdrop-blur-sm border border-slate-600/50 rounded-2xl rounded-tl-none'}`}>

                    {/* Attached Images */}
                    {message.attachedImages && message.attachedImages.length > 0 && (
                        <div className="flex flex-wrap gap-2 mb-3">
                            {message.attachedImages.map((imgSrc, index) => (
                                <div key={index} className="relative group">
                                    <img
                                        src={imgSrc}
                                        alt={`Attachment ${index + 1}`}
                                        className="max-w-xs max-h-60 rounded-lg border border-slate-600/50 object-cover cursor-pointer hover:opacity-90 transition-opacity"
                                        onClick={() => openMedia(imgSrc, 'image')}
                                    />
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Attached Audio */}
                    {message.attachedAudio && message.attachedAudio.length > 0 && (
                        <div className="flex flex-col gap-2 mb-3">
                            {message.attachedAudio.map((src, index) => (
                                <div key={index} className="flex items-center gap-2">
                                    <audio controls src={src} className="w-full max-w-xs" />
                                    <button
                                        onClick={() => openMedia(src, 'audio')}
                                        className="p-2 text-slate-300 hover:text-white hover:bg-white/10 rounded-full transition-colors"
                                        title="Expand Audio"
                                    >
                                        <MaximizeIcon className="w-5 h-5" />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Attached Videos */}
                    {message.attachedVideos && message.attachedVideos.length > 0 && (
                        <div className="flex flex-wrap gap-2 mb-3">
                            {message.attachedVideos.map((src, index) => (
                                <div key={index} className="relative group inline-block">
                                    <video controls src={src} className="max-w-xs max-h-60 rounded-lg border border-slate-600/50" />
                                    <button
                                        onClick={() => openMedia(src, 'video')}
                                        className="absolute top-2 right-2 p-1.5 text-white bg-black/50 hover:bg-black/70 rounded-full opacity-0 group-hover:opacity-100 transition-opacity backdrop-blur-sm"
                                        title="Expand Video"
                                    >
                                        <MaximizeIcon className="w-4 h-4" />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Modern AI Thinking indicator - shows when waiting for stream */}
                    {!isUser && message.text === '' && (
                        <div className="flex items-center gap-2 py-2">
                            {/* Animated sparkle/brain icon */}
                            <div className="relative">
                                <svg
                                    className="w-5 h-5 text-violet-400 animate-pulse"
                                    fill="none"
                                    viewBox="0 0 24 24"
                                    stroke="currentColor"
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={1.5}
                                        d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z"
                                    />
                                </svg>
                                {/* Glow effect */}
                                <div className="absolute inset-0 bg-violet-500/30 blur-md rounded-full animate-ping" style={{ animationDuration: '2s' }} />
                            </div>
                            {/* Thinking text with gradient */}
                            <span className="text-sm font-medium bg-gradient-to-r from-violet-400 via-sky-400 to-violet-400 bg-clip-text text-transparent">
                                Thinking...
                            </span>
                            {/* Subtle animated dots */}
                            <div className="flex gap-0.5">
                                <span className="w-1 h-1 bg-sky-400/60 rounded-full animate-pulse" style={{ animationDelay: '0ms' }} />
                                <span className="w-1 h-1 bg-sky-400/60 rounded-full animate-pulse" style={{ animationDelay: '200ms' }} />
                                <span className="w-1 h-1 bg-sky-400/60 rounded-full animate-pulse" style={{ animationDelay: '400ms' }} />
                            </div>
                        </div>
                    )}

                    {message.text && (
                        <div
                            className={`prose-p:m-0 prose-strong:text-white prose-em:text-slate-300 space-y-3 ${!isUser ? 'pb-8' : ''}`}
                            dangerouslySetInnerHTML={{ __html: parseMarkdown(message.text) }}
                        />
                    )}
                    {!isUser && (
                        <div className={`absolute bottom-2 right-2 z-10 flex items-center gap-1.5 bg-slate-900/40 backdrop-blur-sm p-1 rounded-lg transition-opacity duration-200 border border-slate-600/50 ${isPlaying ? 'opacity-100' : 'opacity-0 group-hover:opacity-100 focus-within:opacity-100'
                            }`}>
                            {/* Show stop button during live playback OR if saved audio exists */}
                            {(isPlaying || message.audioUrl) && (
                                <>
                                    {isPlaying ? (
                                        <button
                                            onClick={onStopAudio}
                                            title="Stop audio"
                                            className="p-1.5 flex items-center justify-center rounded-md bg-red-600/80 hover:bg-red-600 text-white transition-all"
                                        >
                                            <StopIcon className="w-4 h-4" />
                                        </button>
                                    ) : (
                                        <button
                                            onClick={onPlayAudio}
                                            title="Play audio"
                                            className="p-1.5 flex items-center justify-center rounded-md text-slate-300 hover:bg-white/10 hover:text-white transition-all"
                                        >
                                            <PlayIcon className="w-4 h-4" />
                                        </button>
                                    )}
                                </>
                            )}
                            <button onClick={handleCopy} title="Copy text" className="p-1.5 text-slate-300 hover:bg-white/10 hover:text-white rounded-md transition-colors">
                                {showCopied ? <CheckIcon className="w-4 h-4 text-green-400" /> : <CopyIcon className="w-4 h-4" />}
                            </button>
                        </div>
                    )}
                </div>
            </div>
            {isUser && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-700/60 flex items-center justify-center shadow-md">
                    <UserIcon className="w-5 h-5 text-sky-300" />
                </div>
            )}

            <MediaModal
                isOpen={mediaModalOpen}
                onClose={closeMedia}
                src={selectedMedia?.src || ''}
                type={selectedMedia?.type || null}
            />
        </div>
    );
};