import React, { useState, useEffect, useRef, useCallback } from 'react';
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
import { queryTTS, query, queryMcp, uploadDocument, fullAgent, queryMcpTTS, fullAgentMcp, setModel, setVoice, cancelSession, getSessions, createSession, renameSession as apiRenameSession, deleteSession as apiDeleteSession, saveSessionMessages, listDocuments, deleteDocument, queryAgent, queryAgentTTS, fullAgentAgent, listUserStats, createUser, deleteUser, loginUser, updateUser, getModelsCatalog, getSessionSettings } from './services/apiService';
import * as storage from './services/storageService';
import { Message, User, VisemeData, UploadedFile, Session, FullAgentResponse, TTSVoice, QueryMode, AdminUser } from './types';
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
    const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
    const [currentViseme, setCurrentViseme] = useState<string>('X');
    const [activeAudio, setActiveAudio] = useState<HTMLAudioElement | null>(null);
    const [playingAudioId, setPlayingAudioId] = useState<string | null>(null);
    const [spokenResponses, setSpokenResponses] = useState<boolean>(true);
    const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(window.innerWidth >= 1024);
    const [queryMode, setQueryMode] = useState<QueryMode>('agent');

    // New states for model and voice selection
    const [currentModel, setCurrentModel] = useState<string>('gemini-2.5-pro');
    const [availableModels, setAvailableModels] = useState<string[]>([]);
    const [currentVoice, setCurrentVoice] = useState<TTSVoice>(TTSVoice.BF_EMMA);

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
        onConfirm: () => {},
    });


    const { isRecording, startRecording, stopRecording } = useAudioRecorder();
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const animationFrameIdRef = useRef<number | null>(null);
    const abortControllerRef = useRef<AbortController | null>(null);

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

    // Fetch public model catalog so admin-added models are visible to all users
    useEffect(() => {
        const controller = new AbortController();
        const loadModels = async () => {
            if (!currentUser) return;
            try {
                const { available_models } = await getModelsCatalog(currentUser, controller.signal);
                const list = Array.isArray(available_models) ? available_models : [];
                setAvailableModels(list);
                if (list.length > 0 && !list.includes(currentModel)) {
                    setCurrentModel(list[0]);
                }
            } catch (err) {
                console.error('Failed to load models catalog:', err);
            }
        };
        loadModels();
        return () => controller.abort();
    }, [currentUser]);

    const refreshAdminUsers = useCallback(async () => {
        try {
            const stats = await listUserStats();
            const mapped: AdminUser[] = stats.map((u: any) => ({
                id: u.id,
                name: u.username,
                role: u.role === 'admin' ? 'admin' : 'user',
                sessions: u.sessions ?? 0,
                documents: u.documents ?? 0,
                mcpTools: u.mcpTools ?? 0,
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
                    kind: doc.kind as UploadedFile['kind']
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
        const trimmed = text?.trim();
        if (!trimmed) return text;

        // First, try to parse as JSON and convert to user-friendly Markdown
        try {
            const obj = JSON.parse(trimmed);
            const keys = Object.keys(obj || {});
            
            // Handle both old technical format and new user-friendly format
            if (keys.includes('key_findings') || keys.includes('details') || keys.includes('conclusion') || keys.includes('notes') || keys.includes('summary')) {
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

                // Convert notes to Additional Notes
                if (Array.isArray(obj.notes) && obj.notes.length) {
                    lines.push('### Additional Notes');
                    for (const item of obj.notes) {
                        lines.push(`- ${cleanBullet(item)}`);
                    }
                    lines.push('');
                }

                // Add summary if different from conclusion
                if (obj.summary && obj.summary !== obj.conclusion) {
                    lines.push('### Summary');
                    lines.push(cleanBullet(obj.summary));
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

    // Save sessions whenever messages change for the active session
    useEffect(() => {
        if (currentUser && !isAdmin && activeSessionId) {
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
        if (activeAudio) {
            activeAudio.pause();
            activeAudio.onplay = null;
            activeAudio.onended = null;
            activeAudio.onerror = null;
        }
        setCurrentViseme('X');
        setActiveAudio(null);
        setPlayingAudioId(null);
    }, [activeAudio]);

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
        handleStopAudio(); // Stop any currently playing audio and animation.

        const audio = new Audio(audioUrl);
        audioRef.current = audio;
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

        audio.onended = handleStopAudio;
        audio.onerror = () => {
            console.error("Audio playback error.");
            handleStopAudio();
        };

        audio.play().catch(e => {
            console.error("Audio playback failed:", e);
            handleStopAudio();
        });

        // Hide play button after configured TTL by clearing audioUrl from the message
        // This mirrors backend delete-after-serve behavior
        window.setTimeout(() => {
            setMessages(prev => prev.map(m =>
                m.id === messageId ? { ...m, audioUrl: undefined } : m
            ));
        }, DEFAULT_TTS_DELETE_DELAY_SECONDS * 1000);

    }, [handleStopAudio]);

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
            // Load per-session settings to reflect model/voice in sidebar
            try {
                const settings = await getSessionSettings(currentUser, newSession.id);
                setCurrentModel(settings.model_id);
                // Cast voice string to TTSVoice where possible
                setCurrentVoice(settings.voice as TTSVoice);
            } catch (e) {
                console.warn('Failed to load new session settings, using defaults:', e);
            }
        } catch (err) {
            console.error('Failed to create session:', err);
        }
    };

    const handleSelectSession = async (sessionId: string, currentSessions: Session[]) => {
        handleStopAudio();
        const session = currentSessions.find(s => s.id === sessionId);
        if (session) {
            setActiveSessionId(session.id);
            storage.setActiveSessionId(session.id);
            setMessages(session.messages);
            // Fetch persisted per-session settings
            if (currentUser) {
                try {
                    const settings = await getSessionSettings(currentUser, session.id);
                    setCurrentModel(settings.model_id);
                    setCurrentVoice(settings.voice as TTSVoice);
                } catch (e) {
                    console.warn('Failed to load session settings; keeping current selections.', e);
                }
            }
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
            setIsLoading(false); // Give immediate UI feedback
        }
    };

    const handleSendText = async (text: string) => {
        if (!text.trim() || isLoading || !activeSessionId || !currentUser) return;

        const userMessage: Message = { id: crypto.randomUUID(), text, sender: User.USER };
        setMessages(prev => [...prev, userMessage]);
        setIsLoading(true);

        const controller = new AbortController();
        abortControllerRef.current = controller;

        try {
            let assistantMessage: Message;
            const requestParams = { 
                query: text, 
                user_id: currentUser, 
                session_id: activeSessionId,
                system_prompt: systemPrompt
            };

            switch (queryMode) {
                case 'agent':
                    if (spokenResponses) {
                        const data = await queryAgentTTS(requestParams, controller.signal);
                        assistantMessage = {
                            id: crypto.randomUUID(),
                            text: formatAssistantText(data.response),
                            sender: User.ASSISTANT,
                            audioUrl: data.audio_filename ? `${API_BASE_URL}/querytts_audio/${data.audio_filename}?delete=true&delay_seconds=${DEFAULT_TTS_DELETE_DELAY_SECONDS}` : undefined,
                            visemes: data.visemes,
                        };
                        if (assistantMessage.audioUrl && assistantMessage.visemes) {
                            playAudioWithVisemes(assistantMessage.audioUrl, assistantMessage.visemes, assistantMessage.id);
                        }
                    } else {
                        const data = await queryAgent(requestParams, controller.signal);
                        assistantMessage = {
                            id: crypto.randomUUID(),
                            text: formatAssistantText(data.response),
                            sender: User.ASSISTANT,
                        };
                    }
                    break;
                case 'tools':
                    if (spokenResponses) {
                        const data = await queryMcpTTS(requestParams, controller.signal);
                        assistantMessage = {
                            id: crypto.randomUUID(),
                            text: formatAssistantText(data.response),
                            sender: User.ASSISTANT,
                            audioUrl: data.audio_filename ? `${API_BASE_URL}/querytts_audio/${data.audio_filename}?delete=true&delay_seconds=${DEFAULT_TTS_DELETE_DELAY_SECONDS}` : undefined,
                            visemes: data.visemes,
                        };
                        if (assistantMessage.audioUrl && assistantMessage.visemes) {
                            playAudioWithVisemes(assistantMessage.audioUrl, assistantMessage.visemes, assistantMessage.id);
                        }
                    } else {
                        const data = await queryMcp(requestParams, controller.signal);
                        assistantMessage = {
                            id: crypto.randomUUID(),
                            text: formatAssistantText(data.response),
                            sender: User.ASSISTANT,
                        };
                    }
                    break;
                case 'direct':
                default:
                    if (spokenResponses) {
                        const data = await queryTTS(requestParams, controller.signal);
                        assistantMessage = {
                            id: crypto.randomUUID(),
                            text: formatAssistantText(data.response),
                            sender: User.ASSISTANT,
                            audioUrl: data.audio_filename ? `${API_BASE_URL}/querytts_audio/${data.audio_filename}?delete=true&delay_seconds=${DEFAULT_TTS_DELETE_DELAY_SECONDS}` : undefined,
                            visemes: data.visemes,
                        };
                        if (assistantMessage.audioUrl && assistantMessage.visemes) {
                            playAudioWithVisemes(assistantMessage.audioUrl, assistantMessage.visemes, assistantMessage.id);
                        }
                    } else {
                        const data = await query(requestParams, controller.signal);
                        assistantMessage = {
                            id: crypto.randomUUID(),
                            text: formatAssistantText(data.response),
                            sender: User.ASSISTANT,
                        };
                    }
                    break;
            }
            setMessages(prev => [...prev, assistantMessage]);

        } catch (error: any) {
            if (error.name === 'AbortError') {
                console.log("Generation cancelled by user.");
            } else {
                console.error("Error sending message:", error);
                const errorMessage: Message = {
                    id: crypto.randomUUID(),
                    text: "Sorry, I encountered an error. Please try again.",
                    sender: User.ASSISTANT,
                };
                setMessages(prev => [...prev, errorMessage]);
            }
        } finally {
            setIsLoading(false);
            abortControllerRef.current = null;
        }
    };

    const handleSendAudio = async (audioBlob: Blob) => {
        if (!audioBlob || isLoading || !activeSessionId || !currentUser) return;

        setIsLoading(true);
        const controller = new AbortController();
        abortControllerRef.current = controller;

        try {
            const requestParams = { 
                file: audioBlob, 
                user_id: currentUser, 
                session_id: activeSessionId,
                system_prompt: systemPrompt
            };
            let data: FullAgentResponse;

            switch (queryMode) {
                case 'agent':
                    data = await fullAgentAgent(requestParams, controller.signal);
                    break;
                case 'tools':
                    data = await fullAgentMcp(requestParams, controller.signal);
                    break;
                case 'direct':
                default:
                    data = await fullAgent(requestParams, controller.signal);
                    break;
            }
            
            const userMessage: Message = { id: crypto.randomUUID(), text: `🎤: "${data.text}"`, sender: User.USER };
            const assistantMessage: Message = {
                id: crypto.randomUUID(),
                text: formatAssistantText(data.response),
                sender: User.ASSISTANT,
                audioUrl: data.audio_filename ? `${API_BASE_URL}/querytts_audio/${data.audio_filename}?delete=true&delay_seconds=${DEFAULT_TTS_DELETE_DELAY_SECONDS}` : undefined,
                visemes: data.visemes,
            };

            setMessages(prev => [...prev, userMessage, assistantMessage]);

            if (assistantMessage.audioUrl && assistantMessage.visemes) {
                playAudioWithVisemes(assistantMessage.audioUrl, assistantMessage.visemes, assistantMessage.id);
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
                };
                setMessages(prev => [...prev, errorMessage]);
            }
        } finally {
            setIsLoading(false);
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
                        setUploadedFiles(prev => prev.map(f => f.id === upload.id ? { ...f, status: 'error' } : f));
                    });
            });
            // Allow selecting the same file again by clearing input value
            try {
                inputEl.value = '';
            } catch {}
        }
    };

    const handleDeleteDocument = async (filename: string, kind?: UploadedFile['kind']) => {
        if (!currentUser) return;
        try {
            await deleteDocument({ user_id: currentUser, filename, kind });
            setUploadedFiles(prev => prev.filter(f => !(f.file.name === filename && (kind ? f.kind === kind : true))));
        } catch (err) {
            console.error('Delete document failed:', err);
        }
    };

    const handleAddAdminUser = async (newUser: { name: string; password: string; role: 'user' | 'admin' }) => {
        try {
            await createUser(newUser.name.trim(), newUser.password, newUser.role);
            await refreshAdminUsers();
            setAdminView('dashboard');
        } catch (err) {
            showAlert('Error', 'Failed to create user.');
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
        } catch (err) {
            showAlert('Error', 'Failed to update user.');
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
                } catch (err) {
                    showAlert('Error', 'Failed to delete user.');
                    console.error('Delete user failed:', err);
                }
            }
        );
    };
    
    const isSpeaking = !!activeAudio || isRecording;
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
                    availableModels={availableModels}
                    queryMode={queryMode}
                />
                <main className={`flex flex-col flex-1 h-screen overflow-hidden transition-all duration-300 ease-in-out ${isSidebarOpen ? 'lg:ml-80' : 'lg:ml-0'}`}>
                    <Header 
                        user={currentUsername ?? currentUser ?? ''} 
                        onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)} 
                    />
                    <div className="flex-1 flex flex-col p-4 md:p-6 lg:p-8 overflow-hidden">
                        <ChatWindow 
                            messages={messages} 
                            isLoading={isLoading}
                            playingAudioId={playingAudioId}
                            onPlayAudio={handlePlayAudio}
                            onStopAudio={handleStopAudio}
                        />
                        <div className="pt-4 flex-shrink-0">
                            <div className="flex items-center justify-end gap-6 mb-3">
                                <div className="flex items-center gap-3">
                                    <span className="text-sm font-medium text-slate-400">Spoken Responses</span>
                                    <button
                                        onClick={() => handleSpokenResponsesToggle(!spokenResponses)}
                                        className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-900 ${
                                            spokenResponses ? 'bg-sky-600' : 'bg-slate-600'
                                        }`}
                                        aria-pressed={spokenResponses}
                                    >
                                        <span
                                            aria-hidden="true"
                                            className={`inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                                                spokenResponses ? 'translate-x-5' : 'translate-x-0'
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
                                isLoading={isLoading}
                                queryMode={queryMode}
                                onQueryModeChange={(m) => {
                                    setQueryMode(m);
                                    storage.setQueryMode(m);
                                }}
                                onCancel={handleCancelGeneration}
                            />
                        </div>
                    </div>
                </main>
                {spokenResponses && (
                    <aside className="w-[28rem] flex-shrink-0 bg-slate-900/30 backdrop-blur-2xl border-l border-slate-500/30 hidden lg:flex flex-col p-6">
                        <div className="flex-1 flex items-center justify-center">
                            <AvatarView 
                                isSpeaking={isSpeaking} 
                                currentViseme={currentViseme} 
                                isLoading={isLoading}
                                isConversationStarted={isConversationStarted}
                            />
                        </div>
                    </aside>
                )}
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