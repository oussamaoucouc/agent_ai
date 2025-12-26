import React, { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm-configurable';
import remarkBreaks from 'remark-breaks';
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
const preprocessMarkdown = (raw: string): string => {
    if (!raw) return '';
    let processed = raw;

    // PROTECT CODE BLOCKS: Replace code blocks with placeholders before processing
    // This prevents table/list/URL fixes from corrupting JSON, code, etc.
    const codeBlocks: string[] = [];
    processed = processed.replace(/```[\s\S]*?```/g, (match) => {
        const placeholder = `__CODE_BLOCK_${codeBlocks.length}__`;
        codeBlocks.push(match);
        return placeholder;
    });

    // Also protect inline code
    const inlineCode: string[] = [];
    processed = processed.replace(/`[^`]+`/g, (match) => {
        const placeholder = `__INLINE_CODE_${inlineCode.length}__`;
        inlineCode.push(match);
        return placeholder;
    });

    // STEP 0: Normalize unicode characters
    processed = processed.replace(/[＊⁎✱∗⋆]/g, '*');
    processed = processed.replace(/[‐‑‒–—―−]/g, '-');

    // STEP 0.1: FIX SPLIT HEADERS - Join headers that are broken across lines
    // Pattern: "# **Text" on one line, then "more text**" on next line (with possible blank lines between)
    // This happens when AI outputs break in the middle of a header
    // Handle single newline
    processed = processed.replace(/(^#{1,6}\s+\*\*[^\n*]+)\n+([^\n#*]+\*\*)/gm, '$1 $2');

    // Also fix headers with unclosed bold that continue on next line (no closing **)
    processed = processed.replace(/(^#{1,6}\s+\*\*[^\n*]+)\n+([^\n#*]+$)/gm, '$1 $2');

    // Fix the pattern where "Answer**" is on its own line after a header with unclosed bold
    // This specifically handles: "# **The Resulting\nAnswer**"
    processed = processed.replace(/(^#{1,6}\s*\*\*[^\n]+)\n+(\w+\*\*)/gm, '$1 $2');

    // STEP 0.15: CONVERT HASH HEADERS TO STYLED TEXT
    // Process line by line for more reliable header detection
    const lines = processed.split('\n');
    const processedLines = lines.map(line => {
        // Match lines that start with one or more # characters
        const headerMatch = line.match(/^(#{1,6})\s*(.*)$/);
        if (headerMatch) {
            const content = headerMatch[2].trim();
            if (!content) return ''; // Empty header, remove
            // If already bold, just return content without #
            if (content.startsWith('**') && content.endsWith('**')) {
                return content;
            }
            // Wrap in bold
            return `**${content}**`;
        }
        return line;
    });
    processed = processedLines.join('\n');

    // STEP 0.2: SMART LIST SPLITTING (Informative & Logical)
    // Detects pattern: "Text - **Title**" or "Text - [Source]" which indicates an inline list.
    // We convert this to a properly nested sub-list for better readability.
    // Example: "* Source 1: Desc - **Source 2**: Desc" ->
    // "* Source 1: Desc
    //   - **Source 2**: Desc"

    // 1. Split " - **Title**" pattern (Common in citation lists)
    // SAFEGUARD: Match Word OR closing bracket ] or ) before hyphen
    processed = processed.replace(/([\w\])])\s+-\s+\*\*/g, '$1\n\n  - **');

    // 2. Split " - [Source]" pattern
    processed = processed.replace(/([\w\])])\s+-\s+\[/g, '$1\n\n  - [');

    // STEP 0.1: GENERALIZED URL REPAIR (Handle "https://site. com" pattern)
    // Matches "http://" followed by dotted segments, then a dot+space, then more text.
    // Example: "https://finance. yahoo.com" -> "https://finance.yahoo.com"
    processed = processed.replace(/(https?:\/\/(?:[\w-]+\.)+)\s+([\w-]+)/gi, '$1$2');

    // STEP 0.5: FIX BROKEN URLS - NUCLEAR WHITELIST APPROACH (v3.4 - GENERALIZED)
    // Valid chars: Alphanumeric, - . _ ~ : / ? # [ ] @ ! $ & ' ( ) * + , ; = %
    const allowedUrlChars = /[^a-zA-Z0-9\-._~:/?#[\]@!$&'()*+,;=%]/g;

    // 1. Specific Markdown Links: [Text](URL) or [Text]( URL )
    // We allow optional whitespace \s* after (
    processed = processed.replace(/\]\(\s*(https?:\/\/[^)]+)\)/gi, (match, urlContent) => {
        const cleanUrl = urlContent.replace(allowedUrlChars, '');
        return `](${cleanUrl})`;
    });

    // 2. Generic Parentheses: (https://...)
    processed = processed.replace(/\(\s*(https?:\/\/[^)]+)\)/gi, (match, urlContent) => {
        const cleanUrl = urlContent.replace(allowedUrlChars, '');
        return `(${cleanUrl})`;
    });

    // 3. Brackets and Angle Brackets
    processed = processed.replace(/\[\s*(https?:\/\/[^\]]+)\]/gi, (match, urlContent) => {
        const cleanUrl = urlContent.replace(allowedUrlChars, '');
        return `[${cleanUrl}]`;
    });
    processed = processed.replace(/<\s*(https?:\/\/[^>]+)>/gi, (match, urlContent) => {
        const cleanUrl = urlContent.replace(allowedUrlChars, '');
        return `<${cleanUrl}>`;
    });

    // STEP 4: Sanitize Link Text (Fix for nested parentheses breaking parser)
    // Remove nested parentheses in link text which might confuse some markdown parsers
    processed = processed.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/gi, (match, text, url) => {
        const cleanText = text.replace(/[()]/g, ''); // Remove ( ) from title
        return `[${cleanText}](${url})`;
    });

    // STEP 5: FIX INLINE/MALFORMED TABLES
    // AI outputs tables completely inline without newlines
    // Example: "Text| Col1 | Col2 |---|---| Data1 | Data2 |"

    // Step 5a: Find table separator pattern and add newlines around it
    // Separator: |---| or |:---| or |:---:| etc.
    // The separator MUST have at least 3 dashes/colons
    processed = processed.replace(
        /(\|[^|]*\|)\s*(\|[-:\s]{2,}\|(?:[-:\s]*\|)*)\s*(\|)/g,
        '$1\n$2\n$3'
    );

    // Step 5b: After separator row, add newline before each data row
    // Data rows start with | and end with |
    // Pattern: end of row (|) followed by start of another row (|) with content
    processed = processed.replace(/\|\s*\|\s*(?=[^-:\s|])/g, '|\n|');

    // Step 5c: Ensure blank line before the table starts (for markdown to recognize)
    // Find the header row pattern (| text | text |) followed by separator
    processed = processed.replace(
        /([^\n])(\s*\|[^|\n]+\|[^|\n]*\|)\s*\n\s*(\|[-:\s]+)/g,
        '$1\n\n$2\n$3'
    );

    // Step 5d: Final fix - any remaining || patterns should become |\n|
    // This handles row boundaries that weren't caught
    processed = processed.replace(/\|\|/g, '|\n|');

    // STEP 6: CLEANUP - Remove standalone bullets, asterisks, and dashes on their own lines
    // These are artifacts from malformed markdown (e.g., "• " or "* " without text)
    processed = processed.replace(/^\s*[•\*\-]\s*$/gm, '');

    // Remove multiple consecutive blank lines (more than 2)
    processed = processed.replace(/\n{3,}/g, '\n\n');

    // RESTORE CODE BLOCKS: Put back the protected code blocks and inline code
    inlineCode.forEach((code, i) => {
        processed = processed.replace(`__INLINE_CODE_${i}__`, code);
    });
    codeBlocks.forEach((block, i) => {
        processed = processed.replace(`__CODE_BLOCK_${i}__`, block);
    });

    return processed.trim();
};
/**
 * Extract tool usage...
 */
const getLanguageFromClassName = (className?: string): string => {
    // ...
    return 'text';
};

/**
 * Formats a date string into a localized time string (HH:MM AM/PM)
 */
const formatTime = (dateString?: string) => {
    if (!dateString) return '';
    try {
        const date = new Date(dateString);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
        return '';
    }
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
        // Headers - Distinct sections
        h1: ({ children, ...props }: any) => (
            <h1 className="text-2xl font-bold text-slate-100 mt-8 mb-4 pb-2 border-b border-slate-700/60 flex items-center gap-2" {...props}>
                <span className="w-1.5 h-6 bg-sky-500 rounded-full"></span>
                {children}
            </h1>
        ),
        h2: ({ children, ...props }: any) => (
            <h2 className="text-xl font-semibold text-slate-100 mt-6 mb-3 flex items-center gap-2" {...props}>
                <span className="text-sky-400">#</span>
                {children}
            </h2>
        ),
        h3: ({ children, ...props }: any) => (
            <h3 className="text-lg font-semibold text-sky-200 mt-5 mb-2" {...props}>
                {children}
            </h3>
        ),
        h4: ({ children, ...props }: any) => (
            <h4 className="text-base font-semibold text-sky-300 mt-4 mb-2" {...props}>
                {children}
            </h4>
        ),
        h5: ({ children, ...props }: any) => (
            <h5 className="text-sm font-semibold text-slate-300 mt-3 mb-1 uppercase tracking-wider" {...props}>
                {children}
            </h5>
        ),

        // Paragraphs - improved readability
        p: ({ children, ...props }: any) => (
            <p className="text-slate-300 leading-7 mb-4 last:mb-0" {...props}>
                {children}
            </p>
        ),

        // Strong/Bold - high visibility
        strong: ({ children, ...props }: any) => (
            <strong className="font-bold text-sky-300 bg-sky-900/10 px-0.5 rounded" {...props}>
                {children}
            </strong>
        ),

        // Italic
        em: ({ children, ...props }: any) => (
            <em className="italic text-slate-400" {...props}>
                {children}
            </em>
        ),

        // Lists - spaced out and clear
        ul: ({ children, ...props }: any) => (
            <ul className="my-4 space-y-2 list-disc list-outside pl-5 marker:text-sky-500" {...props}>
                {children}
            </ul>
        ),
        ol: ({ children, ...props }: any) => (
            <ol className="my-4 space-y-2 list-decimal list-outside pl-5 text-slate-300 marker:text-sky-500 marker:font-bold" {...props}>
                {children}
            </ol>
        ),
        li: ({ children, ...props }: any) => (
            <li className="leading-7 text-slate-300 pl-1 [&>h3]:mt-0 [&>h3]:mb-1 [&>strong]:text-sky-300" {...props}>
                {children}
            </li>
        ),

        // Blockquotes - Note/Highlight style
        blockquote: ({ children, ...props }: any) => (
            <blockquote
                className="border-l-4 border-sky-500 pl-4 py-2 my-4 bg-slate-800/50 rounded-r-lg italic text-slate-300 shadow-sm"
                {...props}
            >
                {children}
            </blockquote>
        ),

        // Links - "Smart Chip" style for better visibility
        a: ({ href, children, ...props }: any) => {
            const cleanHref = href ? href.replace(/\s+/g, '') : href;
            const isUtterance = cleanHref && cleanHref.startsWith('http');
            const domain = isUtterance ? new URL(cleanHref).hostname.replace('www.', '') : '';

            // If the link text is the same as the URL (or very close), treat it as a "Source" citation
            const isRawUrl = typeof children?.[0] === 'string' && (children[0].includes('http') || children[0].includes('www'));

            if (isRawUrl && isUtterance) {
                return (
                    <a
                        href={cleanHref}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 px-3 py-1 my-1 rounded-full bg-slate-700/50 hover:bg-sky-900/30 border border-slate-600 hover:border-sky-500/50 text-xs text-sky-300 transition-all group no-underline"
                        {...props}
                    >
                        <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                        <span className="font-medium text-slate-200">{domain}</span>
                        <span className="text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity">↗</span>
                    </a>
                );
            }

            return (
                <a
                    href={cleanHref}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sky-400 hover:text-sky-300 font-medium underline decoration-sky-500/30 underline-offset-4 hover:decoration-sky-500 transition-all"
                    {...props}
                >
                    {children}
                </a>
            );
        },

        // Tables - Card-like container
        table: ({ children, ...props }: any) => (
            <div className="my-6 overflow-hidden rounded-xl border border-slate-700 shadow-xl bg-slate-900/40">
                <table className="min-w-full divide-y divide-slate-700" {...props}>
                    {children}
                </table>
            </div>
        ),
        thead: ({ children, ...props }: any) => (
            <thead className="bg-slate-800" {...props}>
                {children}
            </thead>
        ),
        tbody: ({ children, ...props }: any) => (
            <tbody className="divide-y divide-slate-700/50 bg-transparent" {...props}>
                {children}
            </tbody>
        ),
        tr: ({ children, ...props }: any) => (
            <tr className="hover:bg-slate-800/40 transition-colors" {...props}>
                {children}
            </tr>
        ),
        th: ({ children, ...props }: any) => (
            <th className="px-5 py-3 text-left text-xs font-bold text-slate-100 uppercase tracking-wider" {...props}>
                {children}
            </th>
        ),
        td: ({ children, ...props }: any) => {
            // Reuse the complex table cell URL extracted logic if needed, but simplified here for generic 
            return (
                <td className="px-5 py-4 text-sm text-slate-300 whitespace-pre-wrap leading-relaxed" {...props}>
                    {children}
                </td>
            );
        },

        // Code blocks - Window style
        code: ({ inline, className, children, ...props }: any) => {
            const codeString = String(children).replace(/\n$/, '');
            const hasLanguage = className && className.startsWith('language-');
            const hasNewlines = codeString.includes('\n');
            const isInline = inline === true || (!hasLanguage && !hasNewlines);

            if (isInline) {
                return (
                    <code
                        className="px-1.5 py-0.5 mx-0.5 bg-slate-800/80 text-sky-200 rounded-md text-sm font-mono border border-slate-700/50"
                        {...props}
                    >
                        {children}
                    </code>
                );
            }

            const language = className ? className.replace('language-', '') : 'text';
            return (
                <div className="my-5 rounded-lg overflow-hidden border border-slate-700/60 bg-[#1e1e1e] shadow-2xl">
                    <div className="flex items-center justify-between px-4 py-2 bg-[#2d2d2d] border-b border-black/20">
                        <div className="flex items-center gap-2">
                            <div className="flex gap-1.5">
                                <div className="w-2.5 h-2.5 rounded-full bg-red-500/20"></div>
                                <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/20"></div>
                                <div className="w-2.5 h-2.5 rounded-full bg-green-500/20"></div>
                            </div>
                            <span className="text-xs font-medium text-slate-400 ml-2 uppercase tracking-wide">
                                {language}
                            </span>
                        </div>
                        <button
                            onClick={() => navigator.clipboard.writeText(codeString)}
                            className="text-xs text-slate-400 hover:text-white transition-colors px-2 py-1 rounded hover:bg-white/10"
                        >
                            Copy
                        </button>
                    </div>
                    <pre className="p-4 overflow-x-auto custom-scrollbar">
                        <code className={`text-sm font-mono text-slate-200 ${className || ''}`} {...props}>
                            {children}
                        </code>
                    </pre>
                </div>
            );
        },

        // Images - Polaroid style
        img: ({ src, alt, ...props }: any) => (
            <figure className="my-6 inline-block">
                <div className="p-2 bg-slate-800 rounded-lg shadow-xl border border-slate-700/50">
                    <img
                        src={src}
                        alt={alt}
                        className="max-w-full h-auto rounded"
                        loading="lazy"
                        {...props}
                    />
                </div>
                {alt && <figcaption className="text-center text-xs text-slate-500 mt-2 italic">{alt}</figcaption>}
            </figure>
        ),

        // Horizontal Rule
        hr: ({ ...props }: any) => (
            <div className="relative my-8 py-2">
                <div className="absolute inset-0 flex items-center" aria-hidden="true">
                    <div className="w-full border-t border-slate-700/50"></div>
                </div>
                <div className="relative flex justify-center">
                    <span className="bg-slate-900 px-3 text-slate-500 flex items-center gap-1.5 text-sm">
                        <span className="text-slate-600">⎯</span>
                        <span className="text-sky-500/60">●</span>
                        <span className="text-slate-600">⎯</span>
                    </span>
                </div>
            </div>
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
            <del className="text-slate-500 line-through decoration-slate-500/50" {...props}>
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
                    {message.createdAt && (
                        <span className="text-xs font-normal text-slate-400 ml-1">
                            {formatTime(message.createdAt)}
                        </span>
                    )}
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
                    className={`relative overflow-hidden w-fit max-w-full px-8 py-5 rounded-2xl shadow-2xl backdrop-blur-xl border break-words ${isUser
                        ? 'bg-slate-800/60 border-slate-500/40 rounded-tr-none'
                        : 'bg-slate-800/60 border-slate-500/30 rounded-tl-none'
                        }`}
                    style={{ overflowWrap: 'anywhere', wordBreak: 'break-word' }}
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
                                        remarkPlugins={[[remarkGfm, { autolinkLiteral: false }], remarkBreaks]}
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
