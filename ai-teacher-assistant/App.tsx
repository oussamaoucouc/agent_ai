
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { ChatWindow } from './components/ChatWindow';
import { InputBar } from './components/InputBar';
import { AvatarView } from './components/AvatarView';
import { LoginPage } from './components/LoginPage';
import { useAudioRecorder } from './hooks/useAudioRecorder';
import { queryTTS, query, queryMcp, uploadDocument, fullAgent, queryMcpTTS, fullAgentMcp } from './services/apiService';
import * as storage from './services/storageService';
import { Message, User, VisemeData, UploadedFile, Session, FullAgentResponse } from './types';
import { API_BASE_URL } from './constants';

const createNewSession = (): Session => {
    const now = new Date();
    return {
        id: crypto.randomUUID(),
        name: `Session - ${now.toLocaleString()}`,
        createdAt: now.toISOString(),
        messages: [
            {
                id: crypto.randomUUID(),
                text: "Hello! I am your AI Teacher Assistant. How can I help you learn today?",
                sender: User.ASSISTANT,
            },
        ],
    };
};

const App: React.FC = () => {
    const [currentUser, setCurrentUser] = useState<string | null>(null);
    const [isInitialized, setIsInitialized] = useState<boolean>(false);

    const [sessions, setSessions] = useState<Session[]>([]);
    const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
    const [messages, setMessages] = useState<Message[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
    const [currentViseme, setCurrentViseme] = useState<string>('X');
    const [activeAudio, setActiveAudio] = useState<HTMLAudioElement | null>(null);
    const [playingAudioId, setPlayingAudioId] = useState<string | null>(null);
    const [spokenResponses, setSpokenResponses] = useState<boolean>(true);
    const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);
    const [isToolsActive, setIsToolsActive] = useState<boolean>(false);

    const { isRecording, startRecording, stopRecording } = useAudioRecorder();
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const animationFrameIdRef = useRef<number | null>(null);

    useEffect(() => {
        const user = storage.getCurrentUser();
        if (user) {
            setCurrentUser(user);
        }
        setIsInitialized(true);
    }, []);

    // Load sessions when user logs in
    useEffect(() => {
        if (currentUser) {
            const userSessions = storage.getSessionsForUser(currentUser);
            if (userSessions.length > 0) {
                const sortedSessions = [...userSessions].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
                setSessions(sortedSessions);
                handleSelectSession(sortedSessions[0].id, sortedSessions); 
            } else {
                handleNewSession();
            }
        }
    }, [currentUser]);

    // Save sessions whenever messages change for the active session
    useEffect(() => {
        if (currentUser && activeSessionId && sessions.length > 0) {
            const updatedSessions = sessions.map(session =>
                session.id === activeSessionId ? { ...session, messages } : session
            );
            if (JSON.stringify(updatedSessions) !== JSON.stringify(sessions)) {
                setSessions(updatedSessions);
                storage.saveSessionsForUser(currentUser, updatedSessions);
            }
        }
    }, [messages, activeSessionId, currentUser]);


    const handleLogin = (username: string) => {
        const sanitizedUsername = username.trim();
        if (sanitizedUsername) {
            storage.setCurrentUser(sanitizedUsername);
            setCurrentUser(sanitizedUsername);
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
        setSessions([]);
        setMessages([]);
        setActiveSessionId(null);
        setPlayingAudioId(null);
        setActiveAudio(null);
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

    }, [handleStopAudio]);

    const handleNewSession = () => {
        if (!currentUser) return;
        handleStopAudio();
        const newSession = createNewSession();
        const updatedSessions = [newSession, ...sessions];
        setSessions(updatedSessions);
        setActiveSessionId(newSession.id);
        setMessages(newSession.messages);
        storage.saveSessionsForUser(currentUser, updatedSessions);
    };

    const handleSelectSession = (sessionId: string, currentSessions: Session[]) => {
        handleStopAudio();
        const session = currentSessions.find(s => s.id === sessionId);
        if (session) {
            setActiveSessionId(session.id);
            setMessages(session.messages);
        }
    };
    
    const handleDeleteSession = (sessionId: string) => {
        if (!currentUser || !window.confirm("Are you sure you want to delete this session? This action cannot be undone.")) return;
    
        const remainingSessions = sessions.filter(s => s.id !== sessionId);
        setSessions(remainingSessions);
        storage.saveSessionsForUser(currentUser, remainingSessions);
    
        if (activeSessionId === sessionId) {
            if (remainingSessions.length > 0) {
                const sorted = [...remainingSessions].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
                handleSelectSession(sorted[0].id, sorted);
            } else {
                handleNewSession();
            }
        }
    };

    const handleRenameSession = (sessionId: string, newName: string) => {
        if (!currentUser || !newName.trim()) return;
    
        const updatedSessions = sessions.map(s => 
            s.id === sessionId ? { ...s, name: newName.trim() } : s
        );
        setSessions(updatedSessions);
        storage.saveSessionsForUser(currentUser, updatedSessions);
    };

    const handlePlayAudio = useCallback((message: Message) => {
        if (message.audioUrl && message.visemes) {
            playAudioWithVisemes(message.audioUrl, message.visemes, message.id);
        }
    }, [playAudioWithVisemes]);

    const handleSendText = async (text: string) => {
        if (!text.trim() || isLoading || !activeSessionId || !currentUser) return;

        const userMessage: Message = { id: crypto.randomUUID(), text, sender: User.USER };
        setMessages(prev => [...prev, userMessage]);
        setIsLoading(true);

        try {
            let assistantMessage: Message;
            const requestParams = { query: text, user_id: currentUser, session_id: activeSessionId };

            if (isToolsActive) {
                if (spokenResponses) {
                    const data = await queryMcpTTS(requestParams);
                    assistantMessage = {
                        id: crypto.randomUUID(),
                        text: data.response,
                        sender: User.ASSISTANT,
                        audioUrl: data.audio_filename ? `${API_BASE_URL}/querytts_audio/${data.audio_filename}` : undefined,
                        visemes: data.visemes,
                    };
                    if (assistantMessage.audioUrl && assistantMessage.visemes) {
                        playAudioWithVisemes(assistantMessage.audioUrl, assistantMessage.visemes, assistantMessage.id);
                    }
                } else {
                    const data = await queryMcp(requestParams);
                    assistantMessage = {
                        id: crypto.randomUUID(),
                        text: data.response,
                        sender: User.ASSISTANT,
                    };
                }
            } else {
                if (spokenResponses) {
                    const data = await queryTTS(requestParams);
                    assistantMessage = {
                        id: crypto.randomUUID(),
                        text: data.response,
                        sender: User.ASSISTANT,
                        audioUrl: data.audio_filename ? `${API_BASE_URL}/querytts_audio/${data.audio_filename}` : undefined,
                        visemes: data.visemes,
                    };
                    if (assistantMessage.audioUrl && assistantMessage.visemes) {
                        playAudioWithVisemes(assistantMessage.audioUrl, assistantMessage.visemes, assistantMessage.id);
                    }
                } else {
                    const data = await query(requestParams);
                    assistantMessage = {
                        id: crypto.randomUUID(),
                        text: data.response,
                        sender: User.ASSISTANT,
                    };
                }
            }
            setMessages(prev => [...prev, assistantMessage]);

        } catch (error) {
            console.error("Error sending message:", error);
            const errorMessage: Message = {
                id: crypto.randomUUID(),
                text: "Sorry, I encountered an error. Please try again.",
                sender: User.ASSISTANT,
            };
            setMessages(prev => [...prev, errorMessage]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleSendAudio = async (audioBlob: Blob) => {
        if (!audioBlob || isLoading || !activeSessionId || !currentUser) return;

        setIsLoading(true);

        try {
            const requestParams = { file: audioBlob, user_id: currentUser, session_id: activeSessionId };
            let data: FullAgentResponse;

            if (isToolsActive) {
                data = await fullAgentMcp(requestParams);
            } else {
                data = await fullAgent(requestParams);
            }
            
            const userMessage: Message = { id: crypto.randomUUID(), text: `🎤: "${data.text}"`, sender: User.USER };
            const assistantMessage: Message = {
                id: crypto.randomUUID(),
                text: data.response,
                sender: User.ASSISTANT,
                audioUrl: data.audio_filename ? `${API_BASE_URL}/querytts_audio/${data.audio_filename}` : undefined,
                visemes: data.visemes,
            };

            setMessages(prev => [...prev, userMessage, assistantMessage]);

            if (assistantMessage.audioUrl && assistantMessage.visemes) {
                playAudioWithVisemes(assistantMessage.audioUrl, assistantMessage.visemes, assistantMessage.id);
            }

        } catch (error) {
            console.error("Error with full agent:", error);
            const errorMessage: Message = {
                id: crypto.randomUUID(),
                text: "Sorry, I couldn't process the audio. Please try again.",
                sender: User.ASSISTANT,
            };
            setMessages(prev => [...prev, errorMessage]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleStopRecording = async () => {
        const audioBlob = await stopRecording();
        if (audioBlob) {
            handleSendAudio(audioBlob);
        }
    };

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        if (event.target.files && activeSessionId && currentUser) {
            const files = Array.from(event.target.files);
            // FIX: Explicitly type `file` as `File` to resolve a TypeScript type inference error.
            const newUploads: UploadedFile[] = files.map((file: File) => ({
                id: crypto.randomUUID(),
                file,
                status: 'uploading'
            }));

            setUploadedFiles(prev => [...prev, ...newUploads]);

            newUploads.forEach(upload => {
                uploadDocument({ file: upload.file, user_id: currentUser, session_id: activeSessionId })
                    .then(() => {
                        setUploadedFiles(prev => prev.map(f => f.id === upload.id ? { ...f, status: 'success' } : f));
                    })
                    .catch(err => {
                        console.error("File upload failed:", err);
                        setUploadedFiles(prev => prev.map(f => f.id === upload.id ? { ...f, status: 'error' } : f));
                    });
            });
        }
    };
    
    const isSpeaking = !!activeAudio || isRecording;
    const isConversationStarted = messages.length > 1;

    if (!isInitialized) {
        return null; // Or a loading spinner
    }
    
    if (!currentUser) {
        return <LoginPage onLogin={handleLogin} />;
    }

    return (
        <div className="flex h-screen w-full font-sans bg-gradient-to-br from-gray-900 to-gray-800 relative overflow-hidden">
            {isSidebarOpen && (
                <div 
                    className="absolute inset-0 bg-black/60 z-30"
                    onClick={() => setIsSidebarOpen(false)}
                    aria-hidden="true"
                ></div>
            )}
            <Sidebar 
                isSidebarOpen={isSidebarOpen}
                onClose={() => setIsSidebarOpen(false)}
                uploadedFiles={uploadedFiles} 
                onFileChange={handleFileChange}
                sessions={sessions}
                activeSessionId={activeSessionId}
                onNewSession={handleNewSession}
                onSelectSession={(id) => handleSelectSession(id, sessions)}
                onRenameSession={handleRenameSession}
                onDeleteSession={handleDeleteSession}
                onLogout={handleLogout}
            />
            <main className="flex flex-col flex-1 h-screen overflow-hidden">
                <Header 
                    user={currentUser} 
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
                        <div className="flex items-center justify-end gap-3 mb-3">
                            <span className="text-sm font-medium text-gray-400">Spoken Responses</span>
                            <button
                                onClick={() => setSpokenResponses(!spokenResponses)}
                                className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-gray-900 ${
                                    spokenResponses ? 'bg-sky-600' : 'bg-gray-600'
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
                        <InputBar 
                            onSend={handleSendText} 
                            isRecording={isRecording} 
                            onStartRecording={startRecording} 
                            onStopRecording={handleStopRecording} 
                            isLoading={isLoading}
                            isToolsActive={isToolsActive}
                            onToggleTools={() => setIsToolsActive(!isToolsActive)}
                        />
                    </div>
                </div>
            </main>
            <aside className="w-96 flex-shrink-0 bg-gray-800/30 border-l border-gray-700 hidden lg:flex flex-col p-6">
                <div className="flex-1 flex items-center justify-center">
                    <AvatarView 
                        isSpeaking={isSpeaking} 
                        currentViseme={currentViseme} 
                        isLoading={isLoading}
                        isConversationStarted={isConversationStarted}
                    />
                </div>
            </aside>
        </div>
    );
};

export default App;
