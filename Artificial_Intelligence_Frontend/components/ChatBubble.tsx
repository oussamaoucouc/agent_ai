import React, { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Message, User } from '../types';
import { AssistantIcon, UserIcon, SpeakerIcon, SpeakerOffIcon } from './icons';

interface ChatBubbleProps {
    message: Message;
    isPlaying: boolean;
    isStreaming: boolean;
    onPlayAudio: () => void;
    onStopAudio: () => void;
}

interface ToolCall {
    name: string;
    details: string;
}

/**
 * Parses text to extract tool usage logs and clean the message.
 * Handles patterns like:
 * ```text
 * duckduckgo
 * ```
 * (search) -
 */
const extractToolUsage = (text: string): { cleanText: string; toolCalls: ToolCall[] } => {
    if (!text) return { cleanText: '', toolCalls: [] };

    const toolCalls: ToolCall[] = [];
    let cleanText = text;

    // Regex to capture the specific pattern seen in screenshots
    // Pattern: code block with tool name, followed by optional newline, then (category) -
    // We look for common tool names and the specific log format
    const toolPatterns = [
        { name: 'duckduckgo', regex: /```(?:text)?\s*duckduckgo\s*```\s*\n\s*\(search\) -/gi },
        { name: 'fetch', regex: /```(?:text)?\s*fetch\s*```\s*\n\s*\(internet access\) -/gi },
        { name: 'memory', regex: /```(?:text)?\s*memory\s*```\s*\n\s*\(data management\) -/gi },
        { name: 'notion', regex: /```(?:text)?\s*notion\s*```\s*\n\s*\(database.*?\) -/gi },
        { name: 'sequentialthinking', regex: /```(?:text)?\s*sequentialthinking\s*```\s*\n\s*\(problem-solving\) -/gi },
        // Generic fallback for other tools if they follow the pattern
        { name: 'unknown', regex: /```(?:text)?\s*(\w+)\s*```\s*\n\s*\(([^)]+)\) -/gi }
    ];

    // First pass: specific known tools
    toolPatterns.forEach(pattern => {
        let match;
        // Reset regex just in case
        const regex = new RegExp(pattern.regex);

        // We use a loop to find all occurrences
        while ((match = regex.exec(cleanText)) !== null) {
            const toolName = pattern.name === 'unknown' ? match[1] : pattern.name;
            const toolDetails = pattern.name === 'unknown' ? match[2] : 'Executed';

            toolCalls.push({
                name: toolName,
                details: toolDetails
            });
        }

        // Remove from text
        cleanText = cleanText.replace(regex, '');
    });

    // Clean up excessive newlines left behind
    cleanText = cleanText.replace(/\n{3,}/g, '\n\n').trim();

    return { cleanText, toolCalls };
};

/**
 * Preprocesses markdown text to fix common malformed patterns from AI output.
 * Key fix: Strip orphan ** markers that don't have a matching pair on the same line.
 */
const preprocessMarkdown = (text: string): string => {
    if (!text) return '';

    let processed = text;

    // STEP 0: Normalize unicode characters that look like asterisks but aren't
    // Various unicode asterisk-like characters: ＊ (fullwidth), ⁎ (low asterisk), ✱, etc.
    processed = processed.replace(/[＊⁎✱∗⋆]/g, '*');
    // Normalize unicode hyphens/dashes to ASCII hyphen
    processed = processed.replace(/[‐‑‒–—―−]/g, '-');

    // STEP 1: Remove FALSE bullet markers at start of lines
    // If a line starts with "- " followed by lowercase, it's a continuation, not a bullet
    // "- from January..." -> "from January..."
    processed = processed.replace(/^-\s+([a-z])/gm, '$1');

    // STEP 2: Fix split parentheticals - remove newlines inside parentheses
    processed = processed.replace(/\(([^)]*)\)/g, (match) => {
        return match.replace(/\s*\n+\s*/g, ' ');
    });

    // STEP 3: Unescape escaped asterisks (AI sometimes outputs \* instead of *)
    processed = processed.replace(/\\\*/g, '*');

    // STEP 4: Strip truly orphan single asterisks (NOT part of ** bold)
    // Only strip: word* followed by space/punctuation (e.g., "Apprentice* a" -> "Apprentice a")
    // This preserves **bold** formatting
    processed = processed.replace(/(\w)\*(\s|[.,!?;:])/g, '$1$2');

    // STEP 4: Fix squashed table rows
    processed = processed.replace(/\|\|/g, '|\n|');

    // STEP 5: Fix tables starting on same line as text
    processed = processed.replace(/(^|\n)([^\n|]+)(\|[^|\n]*\|[^|\n]*\|)/g, '$1$2\n\n$3');

    // STEP 6: Fix inline section headers ("Header: - Subheader:" pattern)
    // Triggers on sentence-ending punctuation OR colon before " - "
    processed = processed.replace(/([.!?:)])\s*-\s+(\*{0,2}[A-Z])/g, '$1\n\n- $2');

    // STEP 7: Fix run-on sentence spacing (e.g., "Hello.World" -> "Hello. World")
    processed = processed.replace(/([.!?])([A-Za-z])/g, '$1 $2');

    // STEP 8: Strip stray asterisks after colons (e.g., "Title:*" -> "Title:")
    processed = processed.replace(/:(\*+)(\s|$)/g, ':$2');

    // STEP 9: Fix headers with no space after #
    processed = processed.replace(/^(#{1,6})([^#\s])/gm, '$1 $2');

    // STEP 10: Fix headers merged with bold
    processed = processed.replace(/^(#{1,6})\s*\*\*/gm, '$1 **');

    // STEP 11: Fix orphan ** markers (unbalanced bold)
    // Process line by line: if a line has odd number of **, strip ALL ** from that line
    // This handles cases like "**Header:" which has only opening bold
    processed = processed.split('\n').map(line => {
        const doubleAsteriskCount = (line.match(/\*\*/g) || []).length;
        if (doubleAsteriskCount % 2 !== 0) {
            // Odd count = unbalanced, strip all **
            return line.replace(/\*\*/g, '');
        }
        return line;
    }).join('\n');

    // STEP 12: Strip orphan single * at end of lines
    processed = processed.replace(/\s\*\s*$/gm, '');
    processed = processed.replace(/\.\s*\*$/gm, '.');

    // STEP 13: Remove empty bullet points
    processed = processed.replace(/^[-•*]\s*$/gm, '');

    // STEP 14: Normalize multiple consecutive blank lines
    processed = processed.replace(/\n{3,}/g, '\n\n');

    // STEP 15: Ensure code blocks have proper line breaks
    processed = processed.replace(/```(\w+)([^\n])/g, '```$1\n$2');

    // STEP 16: Close any trailing incomplete code fence
    if ((processed.match(/```/g) || []).length % 2 !== 0) {
        processed = processed + '\n```';
    }

    return processed.trim();
};


/**
 * Extract language from code block className
 */
const getLanguageFromClassName = (className?: string): string => {
    if (!className) return 'text';
    const match = className.match(/language-(\w+)/);
    return match ? match[1] : 'text';
};

/**
 * ChatBubble component with comprehensive markdown rendering support.
 * Handles all standard markdown plus GitHub Flavored Markdown (GFM) features.
 */
export const ChatBubble: React.FC<ChatBubbleProps> = ({
    message,
    isPlaying,
    isStreaming,
    onPlayAudio,
    onStopAudio,
}) => {
    const isUser = message.sender === User.USER;
    const [isToolsExpanded, setIsToolsExpanded] = useState(false);

    // Process text to extract tools and fix markdown
    const { cleanText, toolCalls } = useMemo(() => {
        if (isUser) return { cleanText: message.text, toolCalls: [] };

        // 1. Extract tool usage first
        const { cleanText: textWithoutTools, toolCalls: extractedTools } = extractToolUsage(message.text);

        // 2. Then preprocess the remaining markdown
        const finalProcessedText = preprocessMarkdown(textWithoutTools);

        return { cleanText: finalProcessedText, toolCalls: extractedTools };
    }, [message.text, isUser]);

    // Custom components for react-markdown
    const markdownComponents = useMemo(() => ({
        // Headers with proper styling and hierarchy
        h1: ({ children, ...props }: any) => (
            <h1 className="text-2xl font-bold text-slate-100 mt-6 mb-4 pb-2 border-b border-slate-600/50" {...props}>
                {children}
            </h1>
        ),
        h2: ({ children, ...props }: any) => (
            <h2 className="text-xl font-bold text-slate-100 mt-5 mb-3" {...props}>
                {children}
            </h2>
        ),
        h3: ({ children, ...props }: any) => (
            <h3 className="text-lg font-semibold text-sky-300 mt-4 mb-2" {...props}>
                {children}
            </h3>
        ),
        h4: ({ children, ...props }: any) => (
            <h4 className="text-base font-semibold text-sky-400 mt-3 mb-2" {...props}>
                {children}
            </h4>
        ),
        h5: ({ children, ...props }: any) => (
            <h5 className="text-sm font-semibold text-slate-200 mt-2 mb-1" {...props}>
                {children}
            </h5>
        ),
        h6: ({ children, ...props }: any) => (
            <h6 className="text-sm font-medium text-slate-300 mt-2 mb-1" {...props}>
                {children}
            </h6>
        ),

        // Paragraphs
        p: ({ children, ...props }: any) => (
            <p className="text-slate-200 leading-relaxed mb-2 last:mb-0" {...props}>
                {children}
            </p>
        ),

        // Strong/Bold
        strong: ({ children, ...props }: any) => (
            <strong className="font-semibold text-sky-300" {...props}>
                {children}
            </strong>
        ),

        // Emphasis/Italic
        em: ({ children, ...props }: any) => (
            <em className="italic text-slate-300" {...props}>
                {children}
            </em>
        ),

        // Links
        a: ({ href, children, ...props }: any) => (
            <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sky-400 hover:text-sky-300 underline underline-offset-2 transition-colors duration-200"
                {...props}
            >
                {children}
            </a>
        ),

        // Unordered lists
        ul: ({ children, ...props }: any) => (
            <ul className="list-disc list-outside pl-5 my-2 space-y-1 text-slate-200" {...props}>
                {children}
            </ul>
        ),

        // Ordered lists
        ol: ({ children, ...props }: any) => (
            <ol className="list-decimal list-outside pl-6 my-2 space-y-1 text-slate-200" {...props}>
                {children}
            </ol>
        ),

        // List items
        li: ({ children, ...props }: any) => (
            <li className="leading-relaxed pl-1" {...props}>
                {children}
            </li>
        ),

        // Blockquotes
        blockquote: ({ children, ...props }: any) => (
            <blockquote
                className="border-l-4 border-sky-500/60 pl-4 py-1 my-4 bg-slate-800/40 rounded-r-lg italic text-slate-300"
                {...props}
            >
                {children}
            </blockquote>
        ),

        // Inline code
        code: ({ inline, className, children, ...props }: any) => {
            const codeString = String(children).replace(/\n$/, '');
            const hasLanguage = className && className.startsWith('language-');
            const hasNewlines = codeString.includes('\n');

            // Treat as inline if: explicitly inline, OR no language class AND no newlines
            const isInline = inline === true || (!hasLanguage && !hasNewlines);

            if (isInline) {
                return (
                    <code
                        className="px-2 py-1 mx-0.5 bg-slate-700/80 text-sky-300 rounded text-sm font-mono"
                        {...props}
                    >
                        {children}
                    </code>
                );
            }

            // Block code - with syntax highlighting styling
            const language = getLanguageFromClassName(className);
            return (
                <div className="my-4 rounded-xl overflow-hidden border border-slate-600/50 bg-slate-900/80">
                    {/* Language header */}
                    <div className="flex items-center justify-between px-4 py-2 bg-slate-800/80 border-b border-slate-600/40">
                        <span className="text-xs font-medium text-slate-400 uppercase tracking-wide">
                            {language}
                        </span>
                        <button
                            onClick={() => {
                                navigator.clipboard.writeText(codeString);
                            }}
                            className="text-xs text-slate-400 hover:text-sky-400 transition-colors px-2 py-1 rounded hover:bg-slate-700/50"
                        >
                            Copy
                        </button>
                    </div>
                    {/* Code content */}
                    <pre className="p-4 overflow-x-auto">
                        <code className={`text-sm font-mono text-slate-200 ${className || ''}`} {...props}>
                            {children}
                        </code>
                    </pre>
                </div>
            );
        },

        // Preformatted text wrapper
        pre: ({ children, ...props }: any) => (
            <div {...props}>{children}</div>
        ),

        // Horizontal rule
        hr: ({ ...props }: any) => (
            <hr className="my-6 border-slate-600/50" {...props} />
        ),

        // Tables
        table: ({ children, ...props }: any) => (
            <div className="my-4 overflow-x-auto rounded-lg border border-slate-600/50">
                <table className="min-w-full divide-y divide-slate-600/50" {...props}>
                    {children}
                </table>
            </div>
        ),
        thead: ({ children, ...props }: any) => (
            <thead className="bg-slate-800/60" {...props}>
                {children}
            </thead>
        ),
        tbody: ({ children, ...props }: any) => (
            <tbody className="divide-y divide-slate-700/50 bg-slate-800/30" {...props}>
                {children}
            </tbody>
        ),
        tr: ({ children, ...props }: any) => (
            <tr className="hover:bg-slate-700/30 transition-colors" {...props}>
                {children}
            </tr>
        ),
        th: ({ children, ...props }: any) => (
            <th className="px-4 py-3 text-left text-xs font-semibold text-sky-300 uppercase tracking-wider" {...props}>
                {children}
            </th>
        ),
        td: ({ children, ...props }: any) => (
            <td className="px-4 py-3 text-sm text-slate-200" {...props}>
                {children}
            </td>
        ),

        // Images
        img: ({ src, alt, ...props }: any) => (
            <img
                src={src}
                alt={alt || 'Image'}
                className="max-w-full h-auto rounded-lg my-4 shadow-lg"
                loading="lazy"
                {...props}
            />
        ),

        // Task lists (GFM)
        input: ({ type, checked, ...props }: any) => {
            if (type === 'checkbox') {
                return (
                    <input
                        type="checkbox"
                        checked={checked}
                        disabled
                        className="mr-2 rounded border-slate-500 bg-slate-700 text-sky-500 focus:ring-sky-500/50"
                        {...props}
                    />
                );
            }
            return <input type={type} {...props} />;
        },

        // Strikethrough (GFM)
        del: ({ children, ...props }: any) => (
            <del className="text-slate-500 line-through" {...props}>
                {children}
            </del>
        ),
    }), []);

    return (
        <div className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
            {/* Avatar */}
            <div className="relative flex-shrink-0 w-10 h-10">
                {isUser ? (
                    <>
                        <div className="absolute inset-0 rounded-full bg-slate-600/30 blur-sm"></div>
                        <div className="absolute inset-0 rounded-full bg-slate-800/80 backdrop-blur-sm border border-slate-500/40 flex items-center justify-center shadow-lg">
                            <UserIcon className="w-5 h-5 text-slate-300" />
                        </div>
                    </>
                ) : (
                    <>
                        <div className="absolute inset-1 rounded-full bg-gradient-to-r from-sky-400 via-teal-400 to-cyan-400 blur-sm opacity-20"></div>
                        <div className="absolute inset-0 rounded-full bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-600/50 flex items-center justify-center shadow-xl">
                            <AssistantIcon className="w-5 h-5 text-teal-300" />
                        </div>
                    </>
                )}
            </div>

            {/* Message content */}
            <div className={`flex flex-col gap-2 ${isUser ? 'items-end' : 'items-start'} max-w-[85%]`}>
                {/* Sender name */}
                <div className={`font-semibold text-sm text-slate-200 flex items-center gap-2`}>
                    {isUser ? 'You' : 'Assistant'}
                    {isStreaming && !isUser && (
                        <span className="text-xs font-normal text-sky-400/90 flex items-center gap-2">
                            {/* Modern thinking animation - animated dots with shimmer */}
                            <span className="flex items-center gap-0.5">
                                <span
                                    className="w-1.5 h-1.5 rounded-full bg-gradient-to-r from-sky-400 to-cyan-400"
                                    style={{
                                        animation: 'thinkingDot 1.4s ease-in-out infinite',
                                        animationDelay: '0s'
                                    }}
                                />
                                <span
                                    className="w-1.5 h-1.5 rounded-full bg-gradient-to-r from-sky-400 to-cyan-400"
                                    style={{
                                        animation: 'thinkingDot 1.4s ease-in-out infinite',
                                        animationDelay: '0.2s'
                                    }}
                                />
                                <span
                                    className="w-1.5 h-1.5 rounded-full bg-gradient-to-r from-sky-400 to-cyan-400"
                                    style={{
                                        animation: 'thinkingDot 1.4s ease-in-out infinite',
                                        animationDelay: '0.4s'
                                    }}
                                />
                            </span>
                            <span
                                className="relative overflow-hidden"
                                style={{
                                    background: 'linear-gradient(90deg, rgba(56,189,248,0.9) 0%, rgba(34,211,238,1) 50%, rgba(56,189,248,0.9) 100%)',
                                    backgroundSize: '200% 100%',
                                    WebkitBackgroundClip: 'text',
                                    WebkitTextFillColor: 'transparent',
                                    backgroundClip: 'text',
                                    animation: 'shimmerText 2s ease-in-out infinite'
                                }}
                            >
                                Thinking
                            </span>
                        </span>
                    )}
                </div>

                {/* Message bubble */}
                <div
                    className={`relative overflow-hidden w-fit px-8 py-5 rounded-2xl shadow-2xl backdrop-blur-xl border ${isUser
                        ? 'bg-slate-800/60 border-slate-500/40 rounded-tr-none'
                        : 'bg-slate-800/60 border-slate-500/30 rounded-tl-none'
                        }`}
                >
                    {/* Subtle gradient overlay for glassmorphism */}
                    {!isUser && (
                        <div className="absolute inset-0 rounded-2xl rounded-tl-none opacity-20">
                            <div className="absolute inset-0 bg-gradient-to-r from-sky-400/10 via-transparent to-teal-400/10"></div>
                        </div>
                    )}

                    {/* Tool Usage Section */}
                    {toolCalls.length > 0 && !isUser && (
                        <div className="mb-4">
                            <button
                                onClick={() => setIsToolsExpanded(!isToolsExpanded)}
                                className="flex items-center gap-2 text-xs font-medium text-sky-400 hover:text-sky-300 transition-colors bg-slate-700/40 hover:bg-slate-700/60 px-3 py-1.5 rounded-lg border border-slate-600/30 w-full"
                            >
                                <span className="flex-1 flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-teal-400 animate-pulse"></span>
                                    Used {toolCalls.length} tool{toolCalls.length !== 1 ? 's' : ''}
                                </span>
                                <span className={`transform transition-transform duration-200 ${isToolsExpanded ? 'rotate-180' : ''}`}>
                                    ▼
                                </span>
                            </button>

                            {isToolsExpanded && (
                                <div className="mt-2 flex flex-col gap-2 p-3 bg-slate-900/50 rounded-lg border border-slate-600/30">
                                    {toolCalls.map((tool, idx) => (
                                        <div key={idx} className="flex items-start gap-2 text-xs">
                                            <div className="px-1.5 py-0.5 rounded bg-slate-700 text-sky-300 font-mono">
                                                {tool.name}
                                            </div>
                                            <span className="text-slate-400 py-0.5">
                                                {tool.details}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Content */}
                    <div className={`relative ${isUser ? 'text-white' : 'chat-content-with-counter'}`}>
                        {isUser ? (
                            // User messages - simple text, no markdown
                            <p className="leading-relaxed whitespace-pre-wrap">{message.text}</p>
                        ) : (
                            // Assistant messages
                            <>
                                {/* Show skeleton loader when streaming but no content yet */}
                                {isStreaming && !cleanText.trim() ? (
                                    <div className="flex flex-col gap-2 min-w-[200px]">
                                        {/* Skeleton shimmer bars */}
                                        <div
                                            className="h-3 rounded-full bg-slate-600/40"
                                            style={{
                                                width: '85%',
                                                animation: 'skeletonShimmer 1.5s ease-in-out infinite',
                                                background: 'linear-gradient(90deg, rgba(100,116,139,0.3) 25%, rgba(148,163,184,0.4) 50%, rgba(100,116,139,0.3) 75%)',
                                                backgroundSize: '200% 100%'
                                            }}
                                        />
                                        <div
                                            className="h-3 rounded-full bg-slate-600/40"
                                            style={{
                                                width: '70%',
                                                animation: 'skeletonShimmer 1.5s ease-in-out infinite',
                                                animationDelay: '0.15s',
                                                background: 'linear-gradient(90deg, rgba(100,116,139,0.3) 25%, rgba(148,163,184,0.4) 50%, rgba(100,116,139,0.3) 75%)',
                                                backgroundSize: '200% 100%'
                                            }}
                                        />
                                        <div
                                            className="h-3 rounded-full bg-slate-600/40"
                                            style={{
                                                width: '55%',
                                                animation: 'skeletonShimmer 1.5s ease-in-out infinite',
                                                animationDelay: '0.3s',
                                                background: 'linear-gradient(90deg, rgba(100,116,139,0.3) 25%, rgba(148,163,184,0.4) 50%, rgba(100,116,139,0.3) 75%)',
                                                backgroundSize: '200% 100%'
                                            }}
                                        />
                                    </div>
                                ) : (
                                    // Full markdown rendering
                                    <ReactMarkdown
                                        remarkPlugins={[remarkGfm]}
                                        components={markdownComponents}
                                    >
                                        {cleanText}
                                    </ReactMarkdown>
                                )}
                            </>
                        )}
                    </div>

                    {/* Attached media */}
                    {message.attachedImages && message.attachedImages.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                            {message.attachedImages.map((url, idx) => (
                                <img
                                    key={idx}
                                    src={url}
                                    alt={`Attached ${idx + 1}`}
                                    className="max-w-[200px] max-h-[200px] rounded-lg object-cover border border-slate-500/30"
                                />
                            ))}
                        </div>
                    )}
                </div>

                {/* Audio controls for assistant messages */}
                {!isUser && message.audioUrl && (
                    <div className="flex items-center gap-2">
                        <button
                            onClick={isPlaying ? onStopAudio : onPlayAudio}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium
                                       bg-slate-700/60 hover:bg-slate-600/60 border border-slate-500/40
                                       text-slate-200 hover:text-sky-300 transition-all duration-200
                                       shadow-lg hover:shadow-sky-500/10"
                        >
                            {isPlaying ? (
                                <>
                                    <SpeakerOffIcon className="w-4 h-4" />
                                    <span>Stop</span>
                                </>
                            ) : (
                                <>
                                    <SpeakerIcon className="w-4 h-4" />
                                    <span>Play Audio</span>
                                </>
                            )}
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};
