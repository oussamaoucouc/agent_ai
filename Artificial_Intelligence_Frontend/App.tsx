

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { WebAudioQueue } from './WebAudioQueue';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { ChatWindow } from './components/ChatWindow';
import { InputBar } from './components/InputBar';
import { AvatarView } from './components/AvatarView';
import { LoginPage } from './components/LoginPage';
import { DashboardPage } from './components/DashboardPage';
import { ConfigPage } from './components/ConfigPage';
import { AddUserPage } from './components/AddUserPage';
import { EditUserPage } from './components/EditUserPage';
import { Modal } from './components/Modal';
import { useAudioRecorder } from './hooks/useAudioRecorder';
import { queryTTS, query, queryMcp, uploadDocument, fullAgent, queryMcpTTS, fullAgentMcp, setModel, setVoice, cancelSession, getSessions, createSession, renameSession as apiRenameSession, deleteSession as apiDeleteSession, saveSessionMessages, listDocuments, deleteDocument, queryAgent, queryAgentTTS, fullAgentAgent, listUserStats, createUser, deleteUser, loginUser, updateUser, getSessionSettings, getMcpToolsCatalog, setMcpTools, getMcpStdioCatalog, setMcpStdioTools, getConfig, getModelsLabeledCatalog, getVoicesLabeledCatalog } from './services/apiService';
import * as storage from './services/storageService';
import { Message, User, VisemeData, UploadedFile, Session, FullAgentResponse, TTSVoice, QueryMode, AdminUser, McpToolItem, McpStdioItem, LabeledItem, MediaAttachment } from './types';
import { API_BASE_URL } from './constants';

// Default delete-after-serve delay (seconds) must match backend config unless overridden per request
const DEFAULT_TTS_DELETE_DELAY_SECONDS = 120;

// Admin dashboard users will be loaded from backend stats


const systemPrompt = `You are an AI Assistant. Your goal is to provide clear, structured, and informative answers.

CRITICAL FORMATTING RULES:
- NEVER use JSON format, code blocks, or any programming syntax
- NEVER include curly braces {}, square brackets [], or quotation marks around content
- NEVER use technical field names like "key_findings", "details", "conclusion"
- Always write in natural, conversational language using proper Markdown

Format your response using clean Markdown exactly as follows:

### [Write a Clear, Descriptive Title Here]

### Key Points
- Write your main findings in simple, clear language
- Each point should be easy to understand
- Use natural language, not technical jargon

### Explanation
**Source:** [Mention where this information comes from]

**Context:** [Provide helpful background information that makes the topic easier to understand]

### Summary
[Write a clear, concise conclusion that directly answers the user's question]

### Additional Notes
- [Include any important disclaimers or extra helpful information]
- [Keep this section brief and user-friendly]

Remember: Write as if you're speaking directly to a human. Use simple, clear language and avoid any technical formatting or programming syntax.`;

const AuroraBackground = () => (
    <div aria-hidden="true" className="fixed inset-0 -z-10 overflow-hidden">
        <div className="aurora-blob aurora-blob-1"></div>
        <div className="aurora-blob aurora-blob-2"></div>
        <div className="aurora-blob aurora-blob-3"></div>
        <div className="aurora-blob aurora-blob-4"></div>
    </div>
);



const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = error => reject(error);
    });
};

const App: React.FC = () => {
    const [currentUser, setCurrentUser] = useState<string | null>(null);
    const [currentUsername, setCurrentUsername] = useState<string | null>(null);
    const [isAdmin, setIsAdmin] = useState<boolean>(false);
    const [isInitialized, setIsInitialized] = useState<boolean>(false);
    const [adminView, setAdminView] = useState<'dashboard' | 'addUser' | 'editUser' | 'config'>('dashboard');
    const [adminUsers, setAdminUsers] = useState<AdminUser[]>([]);
    const [editingUser, setEditingUser] = useState<AdminUser | null>(null);

    const [sessions, setSessions] = useState<Session[]>([]);
    const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
    const [messages, setMessages] = useState<Message[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [isGenerating, setIsGenerating] = useState<boolean>(false); // New state to track entire generation process
    const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
    const [currentViseme, setCurrentViseme] = useState<string>('X');
    const [activeAudio, setActiveAudio] = useState<HTMLAudioElement | null>(null);
    const activeAudioRef = useRef<HTMLAudioElement | null>(null);
    const [playingAudioId, setPlayingAudioId] = useState<string | null>(null);
    const [spokenResponses, setSpokenResponses] = useState<boolean>(true);
    const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(storage.getSidebarOpen());
    const [queryMode, setQueryMode] = useState<QueryMode>('agent');

    // Web Audio API queue for perfect gapless playback
    const [isPlayingQueue, setIsPlayingQueue] = useState<boolean>(false);
    const webAudioQueueRef = useRef<WebAudioQueue | null>(null);

    // New states for model and voice selection
    const [currentModel, setCurrentModel] = useState<string>('gemini-2.5-pro');
    const [availableModelsLabeled, setAvailableModelsLabeled] = useState<LabeledItem[]>([]);
    const [currentVoice, setCurrentVoice] = useState<TTSVoice>(TTSVoice.BF_EMMA);
    const [availableVoicesLabeled, setAvailableVoicesLabeled] = useState<LabeledItem[]>([]);
    const [selectedMcpTools, setSelectedMcpTools] = useState<string[]>([]);
    const [mcpToolsCatalog, setMcpToolsCatalog] = useState<McpToolItem[]>([]);
    const [isSettingsSyncing, setIsSettingsSyncing] = useState<boolean>(false);
    const [mcpStdioCatalog, setMcpStdioCatalog] = useState<McpStdioItem[]>([]);
    const [selectedMcpStdio, setSelectedMcpStdio] = useState<string[]>([]);
    const isRefreshingRef = useRef<boolean>(false);


    const [modalConfig, setModalConfig] = useState<{
        isOpen: boolean;
        title: string;
        message: string;
        onConfirm: () => void;
        onCancel?: () => void;
        confirmText?: string;
        cancelText?: string;
        showCancel?: boolean;
    }>({
        isOpen: false,
        title: '',
        message: '',
        onConfirm: () => { },
    });


    const { isRecording, startRecording, stopRecording } = useAudioRecorder();
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const animationFrameIdRef = useRef<number | null>(null);
    const abortControllerRef = useRef<AbortController | null>(null);
    const isStreamingRef = useRef<boolean>(false); // Track streaming to prevent session save spam
    const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);  // Track active streaming message for UI indicator

    const showAlert = (title: string, message: string) => {
        setModalConfig({
            isOpen: true,
            title,
            message,
            onConfirm: () => setModalConfig({ ...modalConfig, isOpen: false }),
            showCancel: false,
        });
    };

    const showConfirmation = (title: string, message: string, onConfirmAction: () => void) => {
        setModalConfig({
            isOpen: true,
            title,
            message,
            onConfirm: () => {
                onConfirmAction();
                setModalConfig({ ...modalConfig, isOpen: false });
            },
            onCancel: () => setModalConfig({ ...modalConfig, isOpen: false }),
            showCancel: true,
            confirmText: 'OK',
            cancelText: 'Annuler',
        });
    };

    useEffect(() => {
        const userId = storage.getCurrentUser();
        const username = storage.getCurrentUsername();
        const role = storage.getCurrentUserRole();
        if (userId) {
            setCurrentUser(userId);
            if (username) setCurrentUsername(username);
            setIsAdmin(role === 'admin');
        }
        setIsInitialized(true);
    }, []);

    useEffect(() => {
        storage.setSidebarOpen(isSidebarOpen);
    }, [isSidebarOpen]);

    useEffect(() => {
        const persistedMode = storage.getQueryMode();
        if (persistedMode === 'agent' || persistedMode === 'direct' || persistedMode === 'tools') {
            setQueryMode(persistedMode);
        }
        setSpokenResponses(storage.getSpokenResponses());
    }, []);

    useEffect(() => {
        if (isAdmin) {
            const persistedView = storage.getAdminView();
            if (persistedView === 'dashboard' || persistedView === 'addUser' || persistedView === 'editUser' || persistedView === 'config') {
                setAdminView(persistedView);
            }
        }
    }, [isAdmin]);

    // Handle session expiration events from apiService
    useEffect(() => {
        const handleSessionExpired = () => {
            // Verify we actually have a user logged in before alerting, to avoid spurious alerts on login page etc (though unlikely if 401 comes from authedFetch)
            if (storage.getCurrentUser()) {
                handleLogout();
                showAlert("Session Expired", "Your session has expired. Please log in again.");
            }
        };

        window.addEventListener('auth:session_expired', handleSessionExpired);
        return () => window.removeEventListener('auth:session_expired', handleSessionExpired);
    }, []);

    // ** Consolidated Configuration Loading **
    // Fetches all configuration catalogs (models, voices, tools) in a single, atomic API call
    // to prevent race conditions and ensure UI consistency.
    const loadAppConfiguration = useCallback(async () => {
        if (!currentUser || isRefreshingRef.current) return;
        isRefreshingRef.current = true;
        try {
            // Fetch individual, user-authorized catalogs in parallel.
            // This fixes a 403 error caused by calling the admin-only getConfig endpoint for all users.
            const [
                modelsLabeledRes,
                voicesLabeledRes,
                toolsRes,
                stdioRes,
            ] = await Promise.all([
                getModelsLabeledCatalog(currentUser),
                getVoicesLabeledCatalog(currentUser),
                getMcpToolsCatalog(currentUser),
                getMcpStdioCatalog(currentUser),
            ]);

            const labeledModelsList = Array.isArray(modelsLabeledRes.items) ? modelsLabeledRes.items : [];
            const voicesLabeledList = Array.isArray(voicesLabeledRes.items) ? voicesLabeledRes.items : [];
            const toolsList = Array.isArray(toolsRes.tools) ? toolsRes.tools : [];
            const stdioList = Array.isArray(stdioRes.tools) ? stdioRes.tools : [];

            setAvailableModelsLabeled(labeledModelsList);
            setAvailableVoicesLabeled(voicesLabeledList);
            setMcpToolsCatalog(toolsList);
            setMcpStdioCatalog(stdioList);

        } catch (e) {
            console.error("Failed to load app configuration:", e);
            showAlert('Configuration Error', 'Could not load application configuration from the server.');
        } finally {
            isRefreshingRef.current = false;
        }
    }, [currentUser]);

    useEffect(() => {
        // Load config when user is available.
        if (currentUser) {
            loadAppConfiguration();
        }
    }, [currentUser, loadAppConfiguration]);

    useEffect(() => {
        // Reload config when updated from admin page.
        const handler = () => {
            loadAppConfiguration();
        };
        window.addEventListener('configUpdated', handler as any);
        return () => window.removeEventListener('configUpdated', handler as any);
    }, [loadAppConfiguration]);


    const refreshAdminUsers = useCallback(async () => {
        try {
            const stats = await listUserStats();
            const mapped: AdminUser[] = stats.map((u: any) => ({
                id: u.id,
                name: u.username,
                role: u.role === 'admin' ? 'admin' : 'user',
                sessions: u.sessions ?? 0,
                documents: u.documents ?? 0,
                mcpTools: (u.mcpTools ?? 0),
                mcpWebTools: (u.mcpWebTools ?? 0),
                mcpLocalTools: (u.mcpLocalTools ?? 0),
                createdAt: u.createdAt,
            }));
            setAdminUsers(mapped);
        } catch (err) {
            console.error('Failed to load user stats:', err);
        }
    }, []);

    // Load persisted uploaded documents for the current user
    useEffect(() => {
        const controller = new AbortController();
        const loadDocs = async () => {
            if (!currentUser || isAdmin) {
                setUploadedFiles([]);
                return;
            }
            try {
                const res = await listDocuments(currentUser, controller.signal);
                const items: UploadedFile[] = (res.documents || []).map((doc) => ({
                    id: crypto.randomUUID(),
                    file: new File([""], doc.filename),
                    status: 'success',
                    kind: doc.kind as UploadedFile['kind'],
                    is_admin_uploaded: doc.is_admin_uploaded,
                    uploaded_by: doc.uploaded_by
                }));
                setUploadedFiles(items);
            } catch (err) {
                console.error('Failed to load persisted documents:', err);
                // Keep existing list if fetch fails
            }
        };
        loadDocs();
        return () => controller.abort();
    }, [currentUser, isAdmin]);

    useEffect(() => {
        if (isAdmin) {
            refreshAdminUsers();
        }
    }, [isAdmin, refreshAdminUsers]);

    // Clean and format AI responses for better user experience
    const formatAssistantText = useCallback((text: string): string => {
        let trimmed = text?.trim();
        if (!trimmed) return text || '';

        // STEP 0: Remove Backend Artifacts (e.g. "web-")
        trimmed = trimmed.replace(/^(web-|API-[\w-]+-)/i, '');

        // First, try to parse as JSON and convert to user-friendly Markdown
        try {
            const obj = JSON.parse(trimmed);
            // ... (keep existing JSON logic if valid, but usually this fails for "web-..." text)
            const keys = Object.keys(obj || {});

            // Handle both old technical format and new user-friendly format
            if (keys.includes('key_findings') || keys.includes('details') || keys.includes('conclusion') || keys.includes('notes') || keys.includes('summary') || keys.includes('title')) {
                const lines: string[] = [];

                // Clean bullet points and format nicely
                const cleanBullet = (val: unknown): string => {
                    const s = String(val ?? '').trim();
                    return s.replace(/^[\-*•–—]\s+/, '');
                };

                // Add a user-friendly title if available
                if (obj.title) {
                    lines.push(`### ${cleanBullet(obj.title)}`);
                    lines.push('');
                }

                // Convert key_findings to Key Points
                if (Array.isArray(obj.key_findings) && obj.key_findings.length) {
                    lines.push('### Key Points');
                    for (const item of obj.key_findings) {
                        lines.push(`- ${cleanBullet(item)}`);
                    }
                    lines.push('');
                }

                // Convert details to Explanation
                if (Array.isArray(obj.details) && obj.details.length) {
                    lines.push('### Explanation');
                    for (const item of obj.details) {
                        const cleanItem = cleanBullet(item);
                        // Handle source and context specially
                        if (cleanItem.toLowerCase().startsWith('source:')) {
                            lines.push(`**Source:** ${cleanItem.substring(7).trim()}`);
                        } else if (cleanItem.toLowerCase().startsWith('context:')) {
                            lines.push(`**Context:** ${cleanItem.substring(8).trim()}`);
                        } else {
                            lines.push(`- ${cleanItem}`);
                        }
                    }
                    lines.push('');
                }

                // Add conclusion as Summary
                if (obj.conclusion) {
                    lines.push('### Summary');
                    lines.push(cleanBullet(obj.conclusion));
                    lines.push('');
                }
                // Add summary if different
                if (obj.summary && obj.summary !== obj.conclusion) {
                    lines.push('### Summary');
                    lines.push(cleanBullet(obj.summary));
                }

                // Convert notes to Additional Notes
                if (Array.isArray(obj.notes) && obj.notes.length) {
                    lines.push('### Additional Notes');
                    for (const item of obj.notes) {
                        lines.push(`- ${cleanBullet(item)}`);
                    }
                    lines.push('');
                }

                return lines.join('\n').trim();
            }
        } catch {
            // Not valid JSON, continue with text cleanup
        }

        // Clean up any remaining JSON-like artifacts in plain text
        let cleanedText = trimmed
            // Remove JSON structure artifacts
            .replace(/^\s*\{\s*$/gm, '')
            .replace(/^\s*\}\s*$/gm, '')
            .replace(/^\s*"[^"]*":\s*\[\s*$/gm, '')
            .replace(/^\s*"[^"]*":\s*"([^"]*)"[,]?\s*$/gm, '$1')
            .replace(/^\s*\]\s*[,]?\s*$/gm, '')
            .replace(/^\s*[,]\s*$/gm, '')
            // Clean up technical field names if they appear in text
            .replace(/key_findings/gi, 'Key Points')
            .replace(/\bdetails\b/gi, 'Explanation')
            .replace(/\bconclusion\b/gi, 'Summary')
            .replace(/\bnotes\b/gi, 'Additional Notes')
            // Remove excessive whitespace
            .replace(/\n\s*\n\s*\n/g, '\n\n')
            .trim();

        // === STRUCTURE INJECTION (USER FRIENDLY FORMATTING) ===

        // 1. Ensure Headers have blank lines before them
        cleanedText = cleanedText.replace(/([^\n])\s*(###\s+)/g, '$1\n\n$2');
        // REMOVED: Aggressive bold regex that broke lists (matched **Title** inside "1. **Title**")
        // cleanedText = cleanedText.replace(/([^\n])\s*(\*\*.*?\*\*)/g, '$1\n\n$2');

        // 2. Ensure Lists have blank lines before them (but NOT between number and content)
        // Only trigger if preceded by punctuation (sentence end) to match "Sentence. 1. Item"
        // Avoids matching "Title - Source" or "Item 1- Item 2" (hyphens in text)
        cleanedText = cleanedText.replace(/([.!?:])\s*(\d+\.\s+)/g, '$1\n$2');
        cleanedText = cleanedText.replace(/([.!?:])\s*(-\s+)/g, '$1\n$2');

        // 3. Fix "Interfering Numbers" (The User's specific issue: "...TSLA/2.")
        // If a number-dot-space pattern is glued to previous text (URL or word), force a break.
        // We use \S (non-whitespace) to catch the end of the URL.
        // We look for "2. " (digit dot space) to avoid decimals like "2.5".
        cleanedText = cleanedText.replace(/(\S)(\s*)(\d+\.\s+)/g, '$1\n\n$3');

        // 4. Fix Squashed Sentences after Links
        // Pattern: [Link](url)Sentence -> [Link](url)\n\nSentence
        cleanedText = cleanedText.replace(/(\]\(https?:\/\/[^)]+\))\s*([A-Z])/g, '$1\n\n$2');

        // 5. REPAIR SPLIT LIST ITEMS (The "Gemini Studio" Fix)
        // Fixes: "1.\nTitle" -> "1. Title"
        cleanedText = cleanedText.replace(/^(\d+\.)\s*\n\s*([^\n]+)/gm, '$1 $2');
        // Fixes: "- \nTitle" -> "- Title"
        cleanedText = cleanedText.replace(/^(-\s+)\s*\n\s*([^\n]+)/gm, '$1 $2');

        // 6. FIX FUSED LAST ELEMENT (e.g. ".../quoteThese")
        // Forces a break if a URL is followed by "These", "The", "Here", "In", even if separated by space
        cleanedText = cleanedText.replace(/(https?:\/\/\S+?)(\s*)(These|The|Here|This|In|Stock|Sites|Please|Note)\b/g, '$1\n\n$3');


        // === URL CLEANING (CRITICAL - FIX BROKEN URLS) ===
        // The AI outputs URLs with spaces like "https://finance. yahoo. com/"
        // BUT it might also output "(https://url These sites...)"
        // We must separate the text from the URL before cleaning spaces.

        const dumbUrlClean = (urlContext: string): string => {
            // Check for trailing text (Space + Uppercase) inside the match
            const splitMatch = urlContext.match(/^(.*?)(\s+[A-Z].*)$/);
            if (splitMatch) {
                const urlPart = splitMatch[1];
                const textPart = splitMatch[2];
                return urlPart.replace(/[\s\u00A0\u200B\u2060\uFEFF]+/g, '') + ')' + textPart.trim(); // Close paren, add text
            }
            return urlContext.replace(/[\s\u00A0\u200B\u2060\uFEFF]+/g, '');
        };

        // Clean URLs inside markdown links [text](url)
        cleanedText = cleanedText.replace(
            /\]\(\s*(https?:\/\/[^)]+)\s*\)/gi,
            (match, url) => {
                // Check for trailing text (Space + Uppercase) inside the match
                const splitMatch = url.match(/^(.*?)(\s+[A-Z].*)$/);
                if (splitMatch) {
                    const urlPart = splitMatch[1].replace(/[\s\u00A0\u200B\u2060\uFEFF]+/g, '');
                    const textPart = splitMatch[2];
                    // Reform as: ](URL) Text
                    return `](${urlPart}) ${textPart.trim()}`;
                }
                return `](${url.replace(/[\s\u00A0\u200B\u2060\uFEFF]+/g, '')})`;
            }
        );

        // Clean URLs inside angle brackets <url>
        cleanedText = cleanedText.replace(
            /<\s*(https?:\/\/[^>]+)\s*>/gi,
            (match, url) => {
                const splitMatch = url.match(/^(.*?)(\s+[A-Z].*)$/);
                if (splitMatch) {
                    const urlPart = splitMatch[1].replace(/[\s\u00A0\u200B\u2060\uFEFF]+/g, '');
                    const textPart = splitMatch[2];
                    // Reform as: <URL> Text
                    return `<${urlPart}> ${textPart.trim()}`;
                }
                return `<${url.replace(/[\s\u00A0\u200B\u2060\uFEFF]+/g, '')}>`;
            }
        );

        // === FIX LIST FORMATTING (SQUASHED LIST ITEMS) ===
        // Pattern: "text.1. Item" or "text:1. Item" -> add line break
        cleanedText = cleanedText.replace(/([.!?:])\s*(\d+)\.\s*([A-Za-z\[])/g, '$1\n\n$2. $3');
        // Pattern: "text.- [Link]" -> add line break
        cleanedText = cleanedText.replace(/([.!?:])\s*-\s+\[/g, '$1\n\n- [');

        return cleanedText;
    }, []);

    // Load sessions when user logs in
    useEffect(() => {
        if (currentUser && !isAdmin) {
            (async () => {
                try {
                    const userSessions = await getSessions(currentUser);
                    if (userSessions.length > 0) {
                        const sortedSessions = [...userSessions].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
                        setSessions(sortedSessions);
                        const persistedActive = storage.getActiveSessionId();
                        const match = persistedActive && sortedSessions.find(s => s.id === persistedActive);
                        handleSelectSession(match ? match.id : sortedSessions[0].id, sortedSessions);
                    } else {
                        handleNewSession();
                    }
                } catch (err) {
                    console.error('Failed to load sessions:', err);
                }
            })();
        }
    }, [currentUser, isAdmin]);

    // This effect syncs the active session's settings (model, voice, tools)
    // It runs when the active session changes, or when catalogs (like tools) become available.
    useEffect(() => {
        if (currentUser && !isAdmin && activeSessionId) {
            setIsSettingsSyncing(true);
            (async () => {
                try {
                    const settings = await getSessionSettings(currentUser, activeSessionId);
                    setCurrentModel(settings.model_id);
                    setCurrentVoice(settings.voice as TTSVoice);

                    // If the tool catalog is loaded, map the saved tool URLs back to labels for the UI.
                    // Otherwise, clear the selection; this effect will re-run when the catalog becomes available.
                    if (mcpToolsCatalog.length > 0) {
                        const urls = Array.isArray(settings.mcp_tools_urls) ? settings.mcp_tools_urls : [];

                        // Use fuzzy matching: stored URLs may have extra query params (e.g., Smithery profile URLs)
                        // Match if stored URL starts with catalog URL or catalog URL starts with stored URL base
                        const labels: string[] = [];
                        for (const storedUrl of urls) {
                            for (const tool of mcpToolsCatalog) {
                                const storedBase = storedUrl.split('?')[0].split('&')[0]; // Remove query params  
                                const catalogBase = tool.url.split('?')[0].split('&')[0];
                                if (storedBase.includes(catalogBase) || catalogBase.includes(storedBase) || storedBase === catalogBase) {
                                    labels.push(tool.label);
                                    break;
                                }
                            }
                        }
                        setSelectedMcpTools(labels);
                    } else {
                        setSelectedMcpTools([]);
                    }
                    const cmds = Array.isArray(settings.mcp_stdio_commands) ? settings.mcp_stdio_commands : [];
                    setSelectedMcpStdio(cmds);
                } catch (e) {
                    console.warn('Failed to sync session settings.', e);
                    // On error, clear the tools to prevent showing stale state from a previous session.
                    setSelectedMcpTools([]);
                } finally {
                    setIsSettingsSyncing(false);
                }
            })();
        }
    }, [currentUser, isAdmin, activeSessionId, mcpToolsCatalog]);


    // Save sessions whenever messages change for the active session
    // Skip saving during streaming to prevent excessive API calls
    useEffect(() => {
        if (currentUser && !isAdmin && activeSessionId && !isStreamingRef.current) {
            (async () => {
                try {
                    const saved = await saveSessionMessages(activeSessionId, { user_id: currentUser, messages });
                    setSessions(prev => prev.map(s => s.id === saved.id ? saved : s));
                } catch (err) {
                    console.error('Failed to save messages:', err);
                }
            })();
        }
    }, [messages, activeSessionId, currentUser, isAdmin]);


    const handleLogin = async (username: string, password?: string) => {
        const name = username.trim();
        if (!name || !password) return;
        try {
            const res = await loginUser(name, password);
            if (res.token) {
                storage.setAuthToken(res.token);
            }
            storage.setCurrentUser(res.user_id);
            storage.setCurrentUsername(res.username);
            storage.setCurrentUserRole(res.role === 'admin' ? 'admin' : 'user');
            setCurrentUser(res.user_id);
            setCurrentUsername(res.username);
            setIsAdmin(res.role === 'admin');
            setActiveSessionId(res.session_id || null);
            if (res.role === 'admin') {
                await refreshAdminUsers();
                setAdminView('dashboard');
            }
        } catch (err) {
            showAlert('Login Failed', 'Please check your credentials.');
            console.error('Login failed:', err);
        }
    };

    const handleStopAudio = useCallback(() => {
        if (animationFrameIdRef.current) {
            cancelAnimationFrame(animationFrameIdRef.current);
            animationFrameIdRef.current = null;
        }
        if (activeAudioRef.current) {
            activeAudioRef.current.pause();
            activeAudioRef.current.onplay = null;
            activeAudioRef.current.onended = null;
            activeAudioRef.current.onerror = null;
            activeAudioRef.current = null;
        }

        // Stop Web Audio Queue
        if (webAudioQueueRef.current) {
            webAudioQueueRef.current.stop();
        }

        setCurrentViseme('X');
        setActiveAudio(null);
        setPlayingAudioId(null);

        // Also abort the backend request if still running
        if (abortControllerRef.current) {
            // Tell backend to cancel the active task
            if (currentUser && activeSessionId) {
                cancelSession({ user_id: currentUser, session_id: activeSessionId })
                    .catch((err) => console.debug('Cancel request error (likely already finished):', err));
            }
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }

        // Clear generation state to remove the stop button in InputBar
        setIsLoading(false);
        setIsGenerating(false);
        isStreamingRef.current = false;
        setStreamingMessageId(null);
    }, [currentUser, activeSessionId]);

    const handleLogout = () => {
        handleStopAudio();
        storage.clearCurrentUser();
        setCurrentUser(null);
        setCurrentUsername(null);
        setIsAdmin(false);
        setSessions([]);
        setMessages([]);
        setActiveSessionId(null);
        setPlayingAudioId(null);
        setActiveAudio(null);
        setUploadedFiles([]);
        setAdminView('dashboard'); // Reset admin view on logout
        setEditingUser(null);
    };

    const playAudioWithVisemes = useCallback((audioUrl: string, visemeData: VisemeData, messageId: string) => {
        // Stop current audio playback but DON'T clear the streaming queue
        // This function is for REPLAYING old audio, not stopping ongoing streams
        if (animationFrameIdRef.current) {
            cancelAnimationFrame(animationFrameIdRef.current);
            animationFrameIdRef.current = null;
        }
        if (activeAudioRef.current) {
            activeAudioRef.current.pause();
            activeAudioRef.current.onplay = null;
            activeAudioRef.current.onended = null;
            activeAudioRef.current.onerror = null;
        }

        const audio = new Audio(audioUrl);
        audioRef.current = audio;
        activeAudioRef.current = audio;
        setActiveAudio(audio);
        setPlayingAudioId(messageId);

        // Ensure mouth cues are sorted by start time, as the loop relies on it.
        const sortedMouthCues = [...visemeData.mouthCues].sort((a, b) => a.start - b.start);

        const animate = () => {
            if (audio.paused || audio.ended) {
                setCurrentViseme('X'); // Reset to neutral when done
                return;
            }

            const currentTime = audio.currentTime; // in seconds
            let current = 'X';

            // Find the current viseme by checking the time
            for (const cue of sortedMouthCues) {
                if (cue.start <= currentTime) {
                    current = cue.value;
                } else {
                    break; // Cues are sorted, so we can stop.
                }
            }

            setCurrentViseme(current);

            animationFrameIdRef.current = requestAnimationFrame(animate);
        };

        audio.onplay = () => {
            animationFrameIdRef.current = requestAnimationFrame(animate);
        };

        audio.onended = () => {
            if (animationFrameIdRef.current) {
                cancelAnimationFrame(animationFrameIdRef.current);
                animationFrameIdRef.current = null;
            }
            setCurrentViseme('X');
            setActiveAudio(null);
            setPlayingAudioId(null);
            activeAudioRef.current = null;
        };
        audio.onerror = () => {
            console.error("Audio playback error.");
            if (animationFrameIdRef.current) {
                cancelAnimationFrame(animationFrameIdRef.current);
                animationFrameIdRef.current = null;
            }
            setCurrentViseme('X');
            setActiveAudio(null);
            setPlayingAudioId(null);
            activeAudioRef.current = null;
        };

        audio.play().catch(e => {
            console.error("Audio playback failed:", e);
            if (animationFrameIdRef.current) {
                cancelAnimationFrame(animationFrameIdRef.current);
                animationFrameIdRef.current = null;
            }
            setCurrentViseme('X');
            setActiveAudio(null);
            setPlayingAudioId(null);
            activeAudioRef.current = null;
        });

        // Hide play button after configured TTL by clearing audioUrl from the message
        // This mirrors backend delete-after-serve behavior
        window.setTimeout(() => {
            setMessages(prev => prev.map(m =>
                m.id === messageId ? { ...m, audioUrl: undefined } : m
            ));
        }, DEFAULT_TTS_DELETE_DELAY_SECONDS * 1000);

    }, [handleStopAudio]);

    // Initialize Web Audio Queue on mount
    useEffect(() => {
        if (!webAudioQueueRef.current) {
            console.log('[App] Initializing WebAudioQueue');
            webAudioQueueRef.current = new WebAudioQueue(
                (viseme) => setCurrentViseme(viseme),
                (playing) => setIsPlayingQueue(playing),
                (messageId) => setPlayingAudioId(messageId)
            );
        }

        return () => {
            // Cleanup on unmount
            if (webAudioQueueRef.current) {
                console.log('[App] Disposing WebAudioQueue');
                webAudioQueueRef.current.dispose();
                webAudioQueueRef.current = null;
            }
        };
    }, []);

    // Enqueue audio chunk for playback
    const enqueueAudio = useCallback(async (url: string, visemes: VisemeData, messageId: string) => {
        if (!webAudioQueueRef.current) {
            console.error('[App] WebAudioQueue not initialized');
            return;
        }

        try {
            await webAudioQueueRef.current.enqueue(url, visemes, messageId);
        } catch (error) {
            console.error('[App] Failed to enqueue audio:', error);
        }
    }, []);

    // Stop audio playback

    const handleNewSession = async () => {
        if (!currentUser) return;
        handleStopAudio();
        try {
            const newSession = await createSession({ user_id: currentUser });
            const updatedSessions = [newSession, ...sessions];
            setSessions(updatedSessions);
            setActiveSessionId(newSession.id);
            storage.setActiveSessionId(newSession.id);
            setMessages(newSession.messages);
        } catch (err) {
            console.error('Failed to create session:', err);
        }
    };

    const handleSelectSession = (sessionId: string, currentSessions: Session[]) => {
        handleStopAudio();
        const session = currentSessions.find(s => s.id === sessionId);
        if (session) {
            setActiveSessionId(session.id);
            storage.setActiveSessionId(session.id);
            // Sort messages by createdAt timestamp to ensure proper ordering
            const sortedMessages = [...session.messages].sort((a, b) => {
                const timeA = a.createdAt ? new Date(a.createdAt).getTime() : 0;
                const timeB = b.createdAt ? new Date(b.createdAt).getTime() : 0;
                return timeA - timeB;
            });
            setMessages(sortedMessages);
        }
    };

    const handleDeleteSession = async (sessionId: string) => {
        if (!currentUser) return;

        showConfirmation(
            'Delete Session',
            'Are you sure you want to delete this session? This action cannot be undone.',
            async () => {
                try {
                    await apiDeleteSession(sessionId, { user_id: currentUser });
                    const remainingSessions = sessions.filter(s => s.id !== sessionId);
                    setSessions(remainingSessions);
                    if (activeSessionId === sessionId) {
                        if (remainingSessions.length > 0) {
                            const sorted = [...remainingSessions].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
                            handleSelectSession(sorted[0].id, sorted);
                        } else {
                            handleNewSession();
                        }
                    }
                } catch (err) {
                    console.error('Failed to delete session:', err);
                    showAlert('Error', 'Failed to delete the session. Please try again.');
                }
            }
        );
    };

    const handleSelectedMcpToolsChange = async (labels: string[]) => {
        setSelectedMcpTools(labels);

        if (currentUser && activeSessionId) {
            try {
                await setMcpTools({ user_id: currentUser, session_id: activeSessionId, tool_labels: labels });
            } catch (e) {
                console.warn('Failed to persist MCP tools selection', e);
                showAlert('Sync Error', 'Could not save your tool selection. Please try again.');
            }
        }
    };

    const handleSelectedMcpStdioChange = async (cmds: string[]) => {
        setSelectedMcpStdio(cmds);
        if (currentUser && activeSessionId) {
            try {
                await setMcpStdioTools({ user_id: currentUser, session_id: activeSessionId, commands: cmds });
            } catch (e) {
                console.warn('Failed to persist MCP stdio selection', e);
                showAlert('Sync Error', 'Could not save your stdio selection. Please try again.');
            }
        }
    };

    const handleRenameSession = async (sessionId: string, newName: string) => {
        if (!currentUser || !newName.trim()) return;
        try {
            const renamed = await apiRenameSession(sessionId, { user_id: currentUser, name: newName.trim() });
            const updatedSessions = sessions.map(s => s.id === sessionId ? renamed : s);
            setSessions(updatedSessions);
        } catch (err) {
            console.error('Failed to rename session:', err);
        }
    };

    const handleModelChange = async (model: string) => {
        if (!currentUser || !activeSessionId) return;
        setCurrentModel(model);
        try {
            await setModel({ user_id: currentUser, session_id: activeSessionId, model });
        } catch (error) {
            console.error("Failed to set model on backend:", error);
            // Optionally: show an error message to the user
        }
    };

    const handleVoiceChange = async (voice: TTSVoice) => {
        if (!currentUser || !activeSessionId) return;
        setCurrentVoice(voice);
        try {
            await setVoice({ user_id: currentUser, session_id: activeSessionId, voice });
        } catch (error) {
            console.error("Failed to set voice on backend:", error);
            // Optionally: show an error message to the user
        }
    };

    const handleSpokenResponsesToggle = (enabled: boolean) => {
        setSpokenResponses(enabled);
        storage.setSpokenResponses(enabled);
        if (!enabled) {
            handleStopAudio();
        }
    };

    const handlePlayAudio = useCallback((message: Message) => {
        if (message.audioUrl && message.visemes) {
            playAudioWithVisemes(message.audioUrl, message.visemes, message.id);
        }
    }, [playAudioWithVisemes]);

    const handleCancelGeneration = () => {
        if (abortControllerRef.current) {
            // Proactively tell backend to cancel the active task
            if (currentUser && activeSessionId) {
                cancelSession({ user_id: currentUser, session_id: activeSessionId })
                    .catch((err) => console.debug('Cancel request error (likely already finished):', err));
            }
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
            setIsLoading(false); // Give immediate UI feedback
            setIsGenerating(false); // Stop generation state
            isStreamingRef.current = false; // Mark streaming as complete

            // Clean up any empty messages left from the canceled request
            setMessages(prev => prev.filter(m =>
                m.text.trim().length > 0 ||
                (m.attachedImages?.length ?? 0) > 0 ||
                (m.attachedAudio?.length ?? 0) > 0 ||
                (m.attachedVideos?.length ?? 0) > 0
            ));
        }
    };

    const handleSendText = async (text: string, mediaFiles?: MediaAttachment[]) => {
        if ((!text.trim() && (!mediaFiles || mediaFiles.length === 0)) || isLoading || isGenerating || !activeSessionId || !currentUser) return;

        // Process media files
        const attachedImages: string[] = [];
        const attachedAudio: string[] = [];
        const attachedVideos: string[] = [];

        if (mediaFiles) {
            for (const media of mediaFiles) {
                try {
                    const base64 = await fileToBase64(media.file);
                    if (media.type === 'image') {
                        attachedImages.push(base64);
                    } else if (media.type === 'audio') {
                        attachedAudio.push(base64);
                    } else if (media.type === 'video') {
                        attachedVideos.push(base64);
                    }
                } catch (e) {
                    console.error(`Failed to convert ${media.type} to base64`, e);
                }
            }
        }

        const userMessage: Message = {
            id: crypto.randomUUID(),
            text,
            sender: User.USER,
            attachedImages: attachedImages.length > 0 ? attachedImages : undefined,
            attachedAudio: attachedAudio.length > 0 ? attachedAudio : undefined,
            attachedVideos: attachedVideos.length > 0 ? attachedVideos : undefined,
            createdAt: new Date().toISOString()
        };
        setMessages(prev => {
            // Defensive: duplicate check
            if (prev.some(m => m.id === userMessage.id)) return prev;
            return [...prev, userMessage];
        });
        setIsLoading(true);
        setIsGenerating(true);

        const controller = new AbortController();
        abortControllerRef.current = controller;

        try {
            let assistantMessage: Message;
            const requestParams = {
                query: text,
                user_id: currentUser,
                session_id: activeSessionId,
                system_prompt: systemPrompt,
                images: attachedImages.length > 0 ? attachedImages : undefined,
                audio: attachedAudio.length > 0 ? attachedAudio : undefined,
                videos: attachedVideos.length > 0 ? attachedVideos : undefined
            };

            switch (queryMode) {
                case 'agent':
                    if (spokenResponses) {
                        const streamingMessageId = crypto.randomUUID();
                        assistantMessage = {
                            id: streamingMessageId,
                            text: '',
                            sender: User.ASSISTANT,
                            createdAt: new Date().toISOString()
                        };
                        setMessages(prev => [...prev, assistantMessage]);
                        // Keep isLoading=true so Avatar stays in thinking/generating mode while text streams
                        isStreamingRef.current = true;
                        setStreamingMessageId(streamingMessageId);  // Track for UI indicator

                        // Reset audio queue to allow new audio (in case previous stream was stopped)
                        webAudioQueueRef.current?.reset();

                        // Debounce timer to detect when text streaming ends
                        let textEndTimeout: NodeJS.Timeout | null = null;

                        const data = await queryAgentTTS(requestParams, controller.signal, (chunk) => {
                            // Clear any existing timeout on each new chunk
                            if (textEndTimeout) clearTimeout(textEndTimeout);

                            setMessages(prev => prev.map(m => {
                                if (m.id === streamingMessageId) {
                                    const newText = m.text + chunk;
                                    // Apply full formatting during streaming for better UX
                                    const formatted = formatAssistantText(newText);
                                    return { ...m, text: formatted };
                                }
                                return m;
                            }));

                            // Set timeout - if no more chunks for 400ms, assume text is done
                            textEndTimeout = setTimeout(() => {
                                setStreamingMessageId(null);  // Text streaming complete
                            }, 400);
                        }, (audioFilename, visemes, sentenceIndex) => {
                            // Clear text end timeout since audio is starting
                            if (textEndTimeout) clearTimeout(textEndTimeout);

                            // NEW: Audio chunk callback - enqueue immediately for continuous playback!
                            const audioUrl = `${API_BASE_URL}/querytts_audio/${audioFilename}?delete=true&delay_seconds=${DEFAULT_TTS_DELETE_DELAY_SECONDS}&t=${Date.now()}`;
                            enqueueAudio(audioUrl, visemes, streamingMessageId);

                            // Stop "thinking" animation when first audio starts
                            // Also clear streaming indicator as backup
                            if (sentenceIndex === 0) {
                                setIsLoading(false);
                                setStreamingMessageId(null);  // Backup clear
                            }
                        });

                        // Update with final formatted response
                        setMessages(prev => prev.map(m =>
                            m.id === streamingMessageId
                                ? { ...m, text: formatAssistantText(data.response) || ' ' }
                                : m
                        ));

                        isStreamingRef.current = false;
                        setStreamingMessageId(null);  // Clear streaming indicator
                        // Cleanup any stuck empty messages
                        setMessages(prev => prev.filter(m => m.text.trim().length > 0 || (m.attachedImages?.length ?? 0) > 0 || (m.attachedAudio?.length ?? 0) > 0 || (m.attachedVideos?.length ?? 0) > 0));
                    } else {
                        // Create empty assistant message for streaming
                        const streamingMessageId = crypto.randomUUID();
                        assistantMessage = {
                            id: streamingMessageId,
                            text: '',
                            sender: User.ASSISTANT,
                            createdAt: new Date().toISOString()
                        };
                        setMessages(prev => [...prev, assistantMessage]);
                        // Stop showing loading indicator since we're now streaming
                        setIsLoading(false);
                        // Mark as streaming to prevent session save spam
                        isStreamingRef.current = true;
                        setStreamingMessageId(streamingMessageId);  // Track for UI indicator

                        const data = await queryAgent(requestParams, controller.signal, (chunk) => {
                            // Append chunk and format immediately for smooth display
                            setMessages(prev => prev.map(m => {
                                if (m.id === streamingMessageId) {
                                    const newText = m.text + chunk;
                                    // Apply comprehensive formatting during stream to match final output
                                    // Identify if we're dealing with JSON-like structure keys
                                    const formatted = newText
                                        // Clean potential JSON structure artifacts if they appear raw in stream
                                        .replace(/^\s*\{\s*$/gm, '')
                                        .replace(/^\s*\}\s*$/gm, '')
                                        .replace(/^\s*"[^"]*":\s*\[\s*$/gm, '')
                                        .replace(/^\s*"[^"]*":\s*"([^"]*)"[,]?\s*$/gm, '$1')
                                        .replace(/^\s*\]\s*[,]?\s*$/gm, '')
                                        .replace(/^\s*[,]\s*$/gm, '')
                                        // content cleanup
                                        .replace(/key_findings/gi, 'Key Points')
                                        .replace(/\bdetails\b/gi, 'Explanation')
                                        .replace(/\bconclusion\b/gi, 'Summary')
                                        .replace(/(?<!Additional\s)\bnotes\b/gi, 'Additional Notes');
                                    return { ...m, text: formatted };
                                }
                                return m;
                            }));
                        });

                        // Update with final formatted response (full cleanup)
                        setMessages(prev => prev.map(m =>
                            m.id === streamingMessageId
                                ? { ...m, text: formatAssistantText(data.response) }
                                : m
                        ));

                        // Streaming done - allow session save
                        isStreamingRef.current = false;
                        setStreamingMessageId(null);  // Clear streaming indicator
                        // Skip adding message again since we already added it
                        setIsLoading(false);
                        abortControllerRef.current = null;
                        return;
                    }
                    break;
                case 'tools':
                    if (spokenResponses) {
                        const streamingMessageId = crypto.randomUUID();
                        assistantMessage = {
                            id: streamingMessageId,
                            text: '',
                            sender: User.ASSISTANT,
                        };
                        setMessages(prev => [...prev, assistantMessage]);
                        isStreamingRef.current = true; // Keep isLoading=true for avatar
                        setStreamingMessageId(streamingMessageId);  // Track for UI indicator

                        // Reset audio queue to allow new audio (in case previous stream was stopped)
                        webAudioQueueRef.current?.reset();

                        // Debounce timer to detect when text streaming ends
                        let textEndTimeout: NodeJS.Timeout | null = null;

                        const data = await queryMcpTTS(requestParams, controller.signal, (chunk) => {
                            // Clear any existing timeout on each new chunk
                            if (textEndTimeout) clearTimeout(textEndTimeout);

                            setMessages(prev => prev.map(m => {
                                if (m.id === streamingMessageId) {
                                    const newText = m.text + chunk;
                                    // Apply full formatting during streaming for better UX
                                    const formatted = formatAssistantText(newText);
                                    return { ...m, text: formatted };
                                }
                                return m;
                            }));

                            // Set timeout - if no more chunks for 400ms, assume text is done
                            textEndTimeout = setTimeout(() => {
                                setStreamingMessageId(null);  // Text streaming complete
                            }, 400);
                        }, (audioFilename, visemes, sentenceIndex) => {
                            // Clear text end timeout since audio is starting
                            if (textEndTimeout) clearTimeout(textEndTimeout);

                            // NEW: Audio chunk callback - enqueue immediately for continuous playback!
                            const audioUrl = `${API_BASE_URL}/querytts_audio/${audioFilename}?delete=true&delay_seconds=${DEFAULT_TTS_DELETE_DELAY_SECONDS}`;
                            enqueueAudio(audioUrl, visemes, streamingMessageId);

                            // Stop "thinking" animation when first audio starts
                            // Also clear streaming indicator as backup
                            if (sentenceIndex === 0) {
                                setIsLoading(false);
                                setStreamingMessageId(null);  // Backup clear
                            }
                        });

                        // Update with final formatted response
                        setMessages(prev => prev.map(m =>
                            m.id === streamingMessageId
                                ? { ...m, text: formatAssistantText(data.response) || ' ' }
                                : m
                        ));

                        isStreamingRef.current = false;
                        setStreamingMessageId(null);  // Clear streaming indicator
                        setMessages(prev => prev.filter(m => m.text.trim().length > 0 || (m.attachedImages?.length ?? 0) > 0 || (m.attachedAudio?.length ?? 0) > 0 || (m.attachedVideos?.length ?? 0) > 0));
                    } else {
                        // Create empty assistant message for streaming
                        const streamingMessageId = crypto.randomUUID();
                        assistantMessage = {
                            id: streamingMessageId,
                            text: '',
                            sender: User.ASSISTANT,
                            createdAt: new Date().toISOString()
                        };
                        // Add empty message immediately for smooth UX
                        setMessages(prev => [...prev, assistantMessage]);
                        // Stop showing loading indicator since we're now streaming
                        setIsLoading(false);
                        // Mark as streaming to prevent session save spam
                        isStreamingRef.current = true;
                        setStreamingMessageId(streamingMessageId);  // Track for UI indicator

                        // Stream the response with progressive updates
                        const data = await queryMcp(requestParams, controller.signal, (chunk) => {
                            // Append chunk and format immediately
                            setMessages(prev => prev.map(m => {
                                if (m.id === streamingMessageId) {
                                    const newText = m.text + chunk;
                                    const formatted = newText
                                        // Clean potential JSON structure artifacts if they appear raw in stream
                                        .replace(/^\s*\{\s*$/gm, '')
                                        .replace(/^\s*\}\s*$/gm, '')
                                        .replace(/^\s*"[^"]*":\s*\[\s*$/gm, '')
                                        .replace(/^\s*"[^"]*":\s*"([^"]*)"[,]?\s*$/gm, '$1')
                                        .replace(/^\s*\]\s*[,]?\s*$/gm, '')
                                        .replace(/^\s*[,]\s*$/gm, '')
                                        // content cleanup
                                        .replace(/key_findings/gi, 'Key Points')
                                        .replace(/\bdetails\b/gi, 'Explanation')
                                        .replace(/\bconclusion\b/gi, 'Summary')
                                        .replace(/(?<!Additional\s)\bnotes\b/gi, 'Additional Notes')
                                        // FIX BROKEN URLS - Remove spaces from URLs
                                        // Angle bracket URLs: <https://finance. yahoo. com/>
                                        .replace(/<(https?:\/\/[^>]+)>/gi, (m, url) => `<${url.replace(/\s+/g, '')}>`)
                                        // Markdown links: [text](https://finance. yahoo. com/)
                                        .replace(/\]\((https?:\/\/[^)]+)\)/gi, (m, url) => `](${url.replace(/\s+/g, '')})`);
                                    return { ...m, text: formatted };
                                }
                                return m;
                            }));
                        });

                        // Helper to clean URLs in text (removes spaces inside URLs)
                        const cleanUrlsInText = (text: string | null | undefined): string => {
                            if (!text) return '';
                            let processed = text;

                            // Universal whitespace regex (includes non-breaking spaces, etc.)
                            const wsRegex = /[\s\u00A0\u200B\u200C\u200D\u2060\uFEFF]+/g;

                            // Helper to split "URL Text" patterns inside brackets/parens
                            const smartClean = (fullMatch: string, urlContent: string, wrapper: [string, string]) => {
                                // Check for trailing text (Space + Uppercase) inside the match
                                const splitMatch = urlContent.match(/^(.*?)(\s+[A-Z].*)$/);
                                if (splitMatch) {
                                    const urlPart = splitMatch[1].replace(wsRegex, '');
                                    const textPart = splitMatch[2];
                                    return `${wrapper[0]}${urlPart}${wrapper[1]}${textPart}`; // Put text OUTSIDE wrapper
                                }
                                return `${wrapper[0]}${urlContent.replace(wsRegex, '')}${wrapper[1]}`;
                            };

                            // 1. Angle brackets <url>
                            processed = processed.replace(/<(https?:\/\/[^>]+)>/gi, (m, url) => smartClean(m, url, ['<', '>']));

                            // 2. Parentheses (url)
                            processed = processed.replace(/\((https?:\/\/[^)]+)\)/gi, (m, url) => smartClean(m, url, ['(', ')']));

                            // 3. Square brackets [url]
                            processed = processed.replace(/\[(https?:\/\/[^\]]+)\]/gi, (m, url) => smartClean(m, url, ['[', ']']));

                            return processed;
                        };

                        // Update with final formatted response (full cleanup)
                        console.log('[FINAL-UPDATE] data.response (first 200):', data.response?.substring(0, 200));
                        const contextCleanedText = cleanUrlsInText(formatAssistantText(data.response));
                        console.log('[FINAL-UPDATE] Cleaned Text (first 200):', contextCleanedText?.substring(0, 200));

                        setMessages(prev => prev.map(m =>
                            m.id === streamingMessageId
                                ? { ...m, text: contextCleanedText || ' ' }
                                : m
                        ));

                        // Streaming done - allow session save
                        isStreamingRef.current = false;
                        setStreamingMessageId(null);  // Clear streaming indicator
                        // Skip adding message again since we already added it
                        setIsLoading(false);
                        abortControllerRef.current = null;
                        return;
                    }
                    break;
                case 'direct':
                default:
                    if (spokenResponses) {
                        const streamingMessageId = crypto.randomUUID();
                        assistantMessage = {
                            id: streamingMessageId,
                            text: '',
                            sender: User.ASSISTANT,
                        };
                        setMessages(prev => [...prev, assistantMessage]);
                        isStreamingRef.current = true; // Keep isLoading=true for avatar
                        setStreamingMessageId(streamingMessageId);  // Track for UI indicator

                        // Reset audio queue to allow new audio (in case previous stream was stopped)
                        webAudioQueueRef.current?.reset();

                        // Debounce timer to detect when text streaming ends
                        let textEndTimeout: NodeJS.Timeout | null = null;

                        const data = await queryTTS(requestParams, controller.signal, (chunk) => {
                            // Clear any existing timeout on each new chunk
                            if (textEndTimeout) clearTimeout(textEndTimeout);

                            setMessages(prev => prev.map(m => {
                                if (m.id === streamingMessageId) {
                                    const newText = m.text + chunk;
                                    // Apply full formatting during streaming for better UX
                                    const formatted = formatAssistantText(newText);
                                    return { ...m, text: formatted };
                                }
                                return m;
                            }));

                            // Set timeout - if no more chunks for 400ms, assume text is done
                            textEndTimeout = setTimeout(() => {
                                setStreamingMessageId(null);  // Text streaming complete
                            }, 400);
                        }, (audioFilename, visemes, sentenceIndex) => {
                            // Clear text end timeout since audio is starting
                            if (textEndTimeout) clearTimeout(textEndTimeout);

                            // NEW: Audio chunk callback - enqueue immediately for continuous playback!
                            const audioUrl = `${API_BASE_URL}/querytts_audio/${audioFilename}?delete=true&delay_seconds=${DEFAULT_TTS_DELETE_DELAY_SECONDS}`;
                            enqueueAudio(audioUrl, visemes, streamingMessageId);

                            // Stop "thinking" animation when first audio starts
                            // Also clear streaming indicator as backup
                            if (sentenceIndex === 0) {
                                setIsLoading(false);
                                setStreamingMessageId(null);  // Backup clear
                            }
                        });

                        // Update with final formatted response
                        setMessages(prev => prev.map(m =>
                            m.id === streamingMessageId
                                ? { ...m, text: formatAssistantText(data.response) || ' ' }
                                : m
                        ));

                        isStreamingRef.current = false;
                        setStreamingMessageId(null);  // Clear streaming indicator
                        setMessages(prev => prev.filter(m => m.text.trim().length > 0 || (m.attachedImages?.length ?? 0) > 0 || (m.attachedAudio?.length ?? 0) > 0 || (m.attachedVideos?.length ?? 0) > 0));
                    } else {
                        // Create empty assistant message for streaming
                        const streamingMessageId = crypto.randomUUID();
                        assistantMessage = {
                            id: streamingMessageId,
                            text: '',
                            sender: User.ASSISTANT,
                        };
                        // Add empty message immediately for smooth UX
                        setMessages(prev => [...prev, assistantMessage]);
                        // Stop showing loading indicator since we're now streaming
                        setIsLoading(false);
                        // Mark as streaming to prevent session save spam
                        isStreamingRef.current = true;
                        setStreamingMessageId(streamingMessageId);  // Track for UI indicator

                        // Stream the response with progressive updates
                        const data = await query(requestParams, controller.signal, (chunk) => {
                            // Append chunk and format immediately
                            setMessages(prev => prev.map(m => {
                                if (m.id === streamingMessageId) {
                                    const newText = m.text + chunk;
                                    const formatted = newText
                                        // Clean potential JSON structure artifacts if they appear raw in stream
                                        .replace(/^\s*\{\s*$/gm, '')
                                        .replace(/^\s*\}\s*$/gm, '')
                                        .replace(/^\s*"[^"]*":\s*\[\s*$/gm, '')
                                        .replace(/^\s*"[^"]*":\s*"([^"]*)"[,]?\s*$/gm, '$1')
                                        .replace(/^\s*\]\s*[,]?\s*$/gm, '')
                                        .replace(/^\s*[,]\s*$/gm, '')
                                        // content cleanup
                                        .replace(/key_findings/gi, 'Key Points')
                                        .replace(/\bdetails\b/gi, 'Explanation')
                                        .replace(/\bconclusion\b/gi, 'Summary')
                                        .replace(/(?<!Additional\s)\bnotes\b/gi, 'Additional Notes');
                                    return { ...m, text: formatted };
                                }
                                return m;
                            }));
                        });

                        // Update with final formatted response (full cleanup)
                        setMessages(prev => prev.map(m =>
                            m.id === streamingMessageId
                                ? { ...m, text: formatAssistantText(data.response) }
                                : m
                        ));

                        // Streaming done - allow session save
                        isStreamingRef.current = false;
                        setStreamingMessageId(null);  // Clear streaming indicator
                        // Skip adding message again since we already added it
                        setIsLoading(false);
                        setMessages(prev => prev.filter(m => m.text.trim().length > 0 || (m.attachedImages?.length ?? 0) > 0 || (m.attachedAudio?.length ?? 0) > 0 || (m.attachedVideos?.length ?? 0) > 0));
                        abortControllerRef.current = null;
                        return;
                    }
                    break;
            }

        } catch (error: any) {
            if (error.name === 'AbortError') {
                console.log("Generation cancelled by user.");
            } else {
                console.error("Error sending message:", error);
                const errorMessage: Message = {
                    id: crypto.randomUUID(),
                    text: "Sorry, I encountered an error. Please try again.",
                    sender: User.ASSISTANT,
                    createdAt: new Date().toISOString()
                };
                // Remove any empty "thinking" messages before adding error
                setMessages(prev => [
                    ...prev.filter(m => m.text.trim() !== '' || m.attachedImages?.length || m.attachedAudio?.length || m.attachedVideos?.length),
                    errorMessage
                ]);
            }
        } finally {
            setMessages(prev => prev.filter(m => m.text.trim().length > 0 || (m.attachedImages?.length ?? 0) > 0 || (m.attachedAudio?.length ?? 0) > 0 || (m.attachedVideos?.length ?? 0) > 0));
            setIsLoading(false);
            setIsGenerating(false);
            setStreamingMessageId(null);  // Ensure streaming indicator is cleared
            abortControllerRef.current = null;
        }
    };

    const handleSendAudio = async (audioBlob: Blob) => {
        if (!audioBlob || isLoading || !activeSessionId || !currentUser) return;

        setIsLoading(true);
        setIsGenerating(true);
        const controller = new AbortController();
        abortControllerRef.current = controller;

        isStreamingRef.current = true;
        const streamingMessageId = crypto.randomUUID();
        let assistantMessageAdded = false;

        try {
            const requestParams = {
                file: audioBlob,
                user_id: currentUser,
                session_id: activeSessionId,
                system_prompt: systemPrompt
            };

            const onTranscription = (text: string) => {
                if (assistantMessageAdded) return;
                const userMessageId = crypto.randomUUID();
                const userMessage: Message = { id: userMessageId, text: `🎤: "${text}"`, sender: User.USER };
                const assistantMessage: Message = {
                    id: streamingMessageId,
                    text: '',
                    sender: User.ASSISTANT,
                };

                // Atomic update to ensure correct order
                setMessages(prev => {
                    // Check if we already added this specific interaction to avoid racing
                    if (prev.some(m => m.id === userMessageId || m.id === streamingMessageId)) {
                        return prev;
                    }
                    return [...prev, userMessage, assistantMessage];
                });
                assistantMessageAdded = true;
            };

            const onChunk = (chunk: string) => {
                setMessages(prev => prev.map(m => {
                    if (m.id === streamingMessageId) {
                        const newText = m.text + chunk;
                        const formatted = newText
                            .replace(/^\s*\{\s*$/gm, '')
                            .replace(/^\s*\}\s*$/gm, '')
                            .replace(/^\s*"[^"]*":\s*\[\s*$/gm, '')
                            .replace(/^\s*"[^"]*":\s*"([^"]*)"[,]?\s*$/gm, '$1')
                            .replace(/^\s*\]\s*[,]?\s*$/gm, '')
                            .replace(/^\s*[,]\s*$/gm, '')
                            .replace(/key_findings/gi, 'Key Points')
                            .replace(/\bdetails\b/gi, 'Explanation')
                            .replace(/\bconclusion\b/gi, 'Summary')
                            .replace(/(?<!Additional\s)\bnotes\b/gi, 'Additional Notes');
                        return { ...m, text: formatted };
                    }
                    return m;
                }));
            };

            let data: FullAgentResponse;
            const apiFn = queryMode === 'agent' ? fullAgentAgent : (queryMode === 'tools' ? fullAgentMcp : fullAgent);

            data = await apiFn(requestParams, controller.signal, onChunk, onTranscription);

            const audioUrl = data.audio_filename ? `${API_BASE_URL}/querytts_audio/${data.audio_filename}?delete=true&delay_seconds=${DEFAULT_TTS_DELETE_DELAY_SECONDS}` : undefined;

            setMessages(prev => {
                // If we already added the assistant message (via transcription), just update it
                if (assistantMessageAdded) {
                    return prev.map(m =>
                        m.id === streamingMessageId
                            ? { ...m, text: formatAssistantText(data.response), audioUrl, visemes: data.visemes }
                            : m
                    );
                }

                // If no transcription event happened (e.g. text input or direct file), append both
                // But safeguard against duplicates
                if (prev.some(m => m.id === streamingMessageId)) {
                    return prev.map(m =>
                        m.id === streamingMessageId
                            ? { ...m, text: formatAssistantText(data.response), audioUrl, visemes: data.visemes }
                            : m
                    );
                }

                const userMessage: Message = { id: crypto.randomUUID(), text: `🎤: "${data.text}"`, sender: User.USER };
                const assistantMessage: Message = {
                    id: streamingMessageId,
                    text: formatAssistantText(data.response),
                    sender: User.ASSISTANT,
                    audioUrl,
                    visemes: data.visemes,
                    createdAt: new Date().toISOString()
                };
                return [...prev, userMessage, assistantMessage];
            });

            if (audioUrl && data.visemes) {
                // Short delay to ensure DOM is ready
                setTimeout(() => {
                    playAudioWithVisemes(audioUrl, data.visemes!, streamingMessageId);
                }, 50);
            }

        } catch (error: any) {
            if (error.name === 'AbortError') {
                console.log("Generation cancelled by user.");
            } else {
                console.error("Error with full agent:", error);
                const errorMessage: Message = {
                    id: crypto.randomUUID(),
                    text: "Sorry, I couldn't process the audio. Please try again.",
                    sender: User.ASSISTANT,
                    createdAt: new Date().toISOString()
                };
                setMessages(prev => [...prev, errorMessage]);
            }

            setMessages(prev => prev.filter(m => m.text.trim().length > 0 || (m.attachedImages?.length ?? 0) > 0 || (m.attachedAudio?.length ?? 0) > 0 || (m.attachedVideos?.length ?? 0) > 0));
            setIsLoading(false);
            setIsGenerating(false);
            isStreamingRef.current = false;
            abortControllerRef.current = null;
        }
    };

    const handleStopRecording = async () => {
        const audioBlob = await stopRecording();
        if (audioBlob) {
            handleSendAudio(audioBlob);
        }
    };

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const inputEl = event.target;
        if (inputEl.files && activeSessionId && currentUser) {
            const files = Array.from(inputEl.files);

            // Check for duplicates against existing uploadedFiles
            const duplicateFiles = files.filter((file: File) => uploadedFiles.some(existing => existing.file.name === file.name));

            if (duplicateFiles.length > 0) {
                const duplicateNames = duplicateFiles.map((f: File) => f.name).join(', ');
                showAlert('Duplicate File', `The following file(s) already exist: ${duplicateNames}.`);
                inputEl.value = ''; // Reset input
                return;
            }

            // FIX: Explicitly type `file` as `File` to resolve a TypeScript type inference error.
            const newUploads: UploadedFile[] = files.map((file: File) => ({
                id: crypto.randomUUID(),
                file,
                status: 'uploading'
            }));

            setUploadedFiles(prev => [...prev, ...newUploads]);

            newUploads.forEach(upload => {
                uploadDocument({ file: upload.file, user_id: currentUser, session_id: activeSessionId })
                    .then((res) => {
                        setUploadedFiles(prev => prev.map(f => f.id === upload.id ? { ...f, status: 'success', kind: res.kind as UploadedFile['kind'] } : f));
                    })
                    .catch(err => {
                        console.error("File upload failed:", err);
                        const errorMessage = err instanceof Error ? err.message : "Unknown error occurred";
                        showAlert('Upload Failed', errorMessage);
                        setUploadedFiles(prev => prev.map(f => f.id === upload.id ? { ...f, status: 'error' } : f));
                    });
            });
            // Allow selecting the same file again by clearing input value
            try {
                inputEl.value = '';
            } catch { }
        }
    };

    const handleDeleteDocument = async (filename: string, kind?: UploadedFile['kind']) => {
        if (!currentUser) return;

        // Check if the file is in an error or uploading state (i.e. not yet persisted or failed to persist)
        const fileToDelete = uploadedFiles.find(f => f.file.name === filename && (kind ? f.kind === kind : true));
        const isLocalOnly = fileToDelete?.status === 'error' || fileToDelete?.status === 'uploading';

        showConfirmation(
            'Delete Document',
            `Are you sure you want to delete ${filename}?`,
            async () => {
                try {
                    // Only call backend if it was successfully uploaded
                    if (!isLocalOnly) {
                        await deleteDocument({ user_id: currentUser, filename, kind });
                    }
                    setUploadedFiles(prev => prev.filter(f => !(f.file.name === filename && (kind ? f.kind === kind : true))));
                } catch (err) {
                    console.error('Delete document failed:', err);
                    showAlert('Error', 'Failed to delete document.');
                }
            }
        );
    };

    const handleAddAdminUser = async (newUser: { name: string; password: string; role: 'user' | 'admin' }) => {
        try {
            await createUser(newUser.name.trim(), newUser.password, newUser.role);
            await refreshAdminUsers();
            setAdminView('dashboard');
        } catch (err: any) {
            const errorMessage = err.message || 'Failed to create user.';
            showAlert('Error', errorMessage);
            console.error('Create user failed:', err);
        }
    };

    // Edit admin user flow
    const handleEditAdminUser = (user: AdminUser) => {
        setEditingUser(user);
        setAdminView('editUser');
    };

    const handleSaveEditedUser = async (payload: { password: string; role?: 'user' | 'admin' }) => {
        try {
            if (!editingUser) return;
            await updateUser(editingUser.id, payload);
            await refreshAdminUsers();
            setEditingUser(null);
            setAdminView('dashboard');
        } catch (err: any) {
            const errorMessage = err.message || 'Failed to update user.';
            showAlert('Error', errorMessage);
            console.error('Update user failed:', err);
        }
    };

    const handleCancelEditUser = () => {
        setEditingUser(null);
        setAdminView('dashboard');
    };

    useEffect(() => {
        if (isAdmin) {
            storage.setAdminView(adminView);
        }
    }, [adminView, isAdmin]);

    const handleDeleteAdminUser = async (userId: string) => {
        showConfirmation(
            'Delete User',
            'Are you sure you want to delete this user and all their data? This is irreversible.',
            async () => {
                try {
                    await deleteUser(userId);
                    await refreshAdminUsers();
                } catch (err: any) {
                    const errorMessage = err.message || 'Failed to delete user.';
                    showAlert('Error', errorMessage);
                    console.error('Delete user failed:', err);
                }
            }
        );
    };

    const isSpeaking = !!activeAudio || isRecording || isPlayingQueue;
    const isConversationStarted = messages.length > 1;

    const renderPage = () => {
        if (!isInitialized) {
            return (
                <div className="flex items-center justify-center h-screen">
                    <div className="w-8 h-8 border-2 border-t-sky-400 border-r-sky-400 border-b-sky-400 border-l-transparent rounded-full animate-spin"></div>
                </div>
            );
        }

        if (!currentUser) {
            return <LoginPage onLogin={handleLogin} />;
        }

        if (isAdmin) {
            switch (adminView) {
                case 'addUser':
                    return <AddUserPage onAddUser={handleAddAdminUser} onCancel={() => setAdminView('dashboard')} />;
                case 'editUser':
                    return editingUser ? (
                        <EditUserPage
                            userId={editingUser.id}
                            username={editingUser.name}
                            currentRole={editingUser.role}
                            onSave={handleSaveEditedUser}
                            onCancel={handleCancelEditUser}
                        />
                    ) : <DashboardPage
                        users={adminUsers}
                        onLogout={handleLogout}
                        onNavigateToAddUser={() => setAdminView('addUser')}
                        onNavigateToConfig={() => setAdminView('config')}
                        onDeleteUser={handleDeleteAdminUser}
                        onEditUser={handleEditAdminUser}
                        onShowConfirmation={showConfirmation}
                    />;
                case 'config':
                    return <ConfigPage onCancel={() => setAdminView('dashboard')} onShowAlert={(message, title) => showAlert(title, message)} />;
                default:
                    return (
                        <DashboardPage
                            users={adminUsers}
                            onLogout={handleLogout}
                            onNavigateToAddUser={() => setAdminView('addUser')}
                            onNavigateToConfig={() => setAdminView('config')}
                            onDeleteUser={handleDeleteAdminUser}
                            onEditUser={handleEditAdminUser}
                            onShowConfirmation={showConfirmation}
                        />
                    );
            }
        }

        return (
            <div className="flex h-screen w-full font-sans relative overflow-hidden">
                {isSidebarOpen && (
                    <div
                        className="fixed inset-0 bg-black/60 z-30 lg:hidden"
                        onClick={() => setIsSidebarOpen(false)}
                        aria-hidden="true"
                    ></div>
                )}
                <Sidebar
                    isSidebarOpen={isSidebarOpen}
                    onClose={() => setIsSidebarOpen(false)}
                    uploadedFiles={uploadedFiles}
                    onFileChange={handleFileChange}
                    onDeleteDocument={handleDeleteDocument}
                    sessions={sessions}
                    activeSessionId={activeSessionId}
                    onNewSession={handleNewSession}
                    onSelectSession={(id) => handleSelectSession(id, sessions)}
                    onRenameSession={handleRenameSession}
                    onDeleteSession={handleDeleteSession}
                    onLogout={handleLogout}
                    currentModel={currentModel}
                    currentVoice={currentVoice}
                    onModelChange={handleModelChange}
                    onVoiceChange={handleVoiceChange}
                    availableModelsLabeled={availableModelsLabeled}
                    availableVoicesLabeled={availableVoicesLabeled}
                    queryMode={queryMode}
                    mcpToolsCatalog={mcpToolsCatalog}
                    selectedMcpTools={selectedMcpTools}
                    onSelectedMcpToolsChange={handleSelectedMcpToolsChange}
                    mcpStdioCatalog={mcpStdioCatalog}
                    selectedMcpStdio={selectedMcpStdio}
                    onSelectedMcpStdioChange={handleSelectedMcpStdioChange}
                    isSettingsSyncing={isSettingsSyncing}
                    onShowConfirmation={showConfirmation}
                />
                <main className={`flex flex-col flex-1 h-screen overflow-hidden transition-all duration-300 ease-in-out ${isSidebarOpen ? 'lg:ml-80' : 'lg:ml-0'}`}>
                    <Header
                        user={currentUsername ?? currentUser ?? ''}
                        onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
                    />
                    <div className="flex-1 flex flex-col p-4 md:p-6 lg:p-8 overflow-hidden">
                        <ChatWindow
                            messages={messages}
                            isLoading={isLoading && !spokenResponses}
                            isGenerating={isGenerating}
                            playingAudioId={playingAudioId}
                            streamingMessageId={streamingMessageId}
                            onPlayAudio={handlePlayAudio}
                            onStopAudio={handleStopAudio}
                        />
                        <div className="pt-4 flex-shrink-0">
                            <div className="flex items-center justify-end gap-6 mb-3">
                                <div className="flex items-center gap-3">
                                    <span className="text-sm font-medium text-slate-400">Spoken Responses</span>
                                    <button
                                        onClick={() => handleSpokenResponsesToggle(!spokenResponses)}
                                        className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-900 ${spokenResponses ? 'bg-sky-600' : 'bg-slate-600'
                                            }`}
                                        aria-pressed={spokenResponses}
                                    >
                                        <span
                                            aria-hidden="true"
                                            className={`inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${spokenResponses ? 'translate-x-5' : 'translate-x-0'
                                                }`}
                                        />
                                    </button>
                                </div>
                            </div>
                            <InputBar
                                onSend={handleSendText}
                                isRecording={isRecording}
                                onStartRecording={startRecording}
                                onStopRecording={handleStopRecording}
                                isLoading={isGenerating} // Use isGenerating to keep Stop button visible during speech/streaming
                                isPlayingAudio={isPlayingQueue}  // Hide cancel button when audio is playing
                                queryMode={queryMode}
                                onQueryModeChange={(m) => {
                                    setQueryMode(m);
                                    storage.setQueryMode(m);
                                }}
                                onCancel={handleCancelGeneration}
                                supportsImages={availableModelsLabeled.find(m => m.id === currentModel)?.supports_images}
                                supportsAudio={availableModelsLabeled.find(m => m.id === currentModel)?.supports_audio}
                                supportsVideos={availableModelsLabeled.find(m => m.id === currentModel)?.supports_videos}
                            />
                        </div>
                    </div>
                </main>
                {/* Avatar Panel with smooth transition */}
                <aside
                    className={`w-[28rem] flex-shrink-0 bg-slate-900/30 backdrop-blur-2xl border-l border-slate-500/30 hidden lg:flex flex-col p-6 transition-all duration-500 ease-in-out ${spokenResponses
                        ? 'translate-x-0 opacity-100'
                        : 'translate-x-full opacity-0 pointer-events-none absolute right-0 top-0 bottom-0'
                        }`}
                >
                    <div className="flex-1 flex items-center justify-center">
                        <AvatarView
                            isSpeaking={isSpeaking}
                            currentViseme={currentViseme}
                            isLoading={isLoading}
                            isGenerating={isGenerating}
                            isConversationStarted={isConversationStarted}
                            onStopAudio={handleStopAudio}
                        />
                    </div>
                </aside>
            </div>
        );
    };

    return (
        <div className="h-screen w-screen bg-slate-900">
            <AuroraBackground />
            {renderPage()}
            <Modal
                isOpen={modalConfig.isOpen}
                title={modalConfig.title}
                message={modalConfig.message}
                onConfirm={modalConfig.onConfirm}
                onCancel={modalConfig.onCancel}
                confirmText={modalConfig.confirmText}
                cancelText={modalConfig.cancelText}
                showCancel={modalConfig.showCancel}
            />
        </div>
    );
};

export default App;
