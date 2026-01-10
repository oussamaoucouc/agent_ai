import React, { useState, useRef, useEffect } from 'react';
import { UploadedFile, Session, TTSVoice, QueryMode } from '../types';
import * as storage from '../services/storageService';
import { getVoicesCatalog } from '../services/apiService';
import { McpToolItem } from '../types';
import { ModelSelector } from './ModelSelector';
import { VoiceSelector } from './VoiceSelector';
import { ToolsSelector } from './ToolsSelector';
import { DocumentIcon, UploadIcon, SpinnerIcon, CheckIcon, ErrorIcon, PlusIcon, LogoutIcon, ChatIcon, CloseIcon, EditIcon, TrashIcon } from './icons';

interface SidebarProps {
    uploadedFiles: UploadedFile[];
    onFileChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
    onDeleteDocument: (filename: string, kind?: UploadedFile['kind']) => void;
    sessions: Session[];
    activeSessionId: string | null;
    onNewSession: () => void;
    onSelectSession: (sessionId: string) => void;
    onRenameSession: (sessionId: string, newName: string) => void;
    onDeleteSession: (sessionId: string) => void;
    onLogout: () => void;
    isSidebarOpen: boolean;
    onClose: () => void;
    currentModel: string;
    onModelChange: (model: string) => void;
    currentVoice: TTSVoice;
    onVoiceChange: (voice: TTSVoice) => void;
    availableModelsLabeled?: { label: string; id: string; provider?: string }[];
    availableVoicesLabeled?: { label: string; id: string }[];
    queryMode: QueryMode;
    mcpToolsCatalog: McpToolItem[];
    selectedMcpTools: string[];
    onSelectedMcpToolsChange: (labels: string[]) => void;
    mcpStdioCatalog: { label: string; command: string }[];
    selectedMcpStdio: string[];
    onSelectedMcpStdioChange: (cmds: string[]) => void;
    isSettingsSyncing?: boolean;
    onShowConfirmation?: (title: string, message: string, onConfirm: () => void) => void;
}

const StatusIcon: React.FC<{ status: UploadedFile['status'] }> = ({ status }) => {
    switch (status) {
        case 'uploading':
            return <SpinnerIcon className="w-5 h-5 text-sky-400 animate-spin" />;
        case 'success':
            return <CheckIcon className="w-5 h-5 text-green-400" />;
        case 'error':
            return <ErrorIcon className="w-5 h-5 text-red-400" />;
        default:
            return null;
    }
};

const DEFAULT_VOICES: string[] = [];


export const Sidebar: React.FC<SidebarProps> = ({
    uploadedFiles,
    onFileChange,
    onDeleteDocument,
    sessions,
    activeSessionId,
    onNewSession,
    onSelectSession,
    onRenameSession,
    onDeleteSession,
    onLogout,
    isSidebarOpen,
    onClose,
    currentModel,
    onModelChange,
    currentVoice,
    onVoiceChange,
    availableModelsLabeled,
    availableVoicesLabeled,
    queryMode,
    mcpToolsCatalog,
    selectedMcpTools,
    onSelectedMcpToolsChange,
    mcpStdioCatalog,
    selectedMcpStdio,
    onSelectedMcpStdioChange,
    isSettingsSyncing = false,
    onShowConfirmation,
}) => {
    const [renamingSessionId, setRenamingSessionId] = useState<string | null>(null);
    const [sessionName, setSessionName] = useState('');
    const [fileFilter, setFileFilter] = useState<'all' | 'user' | 'admin'>('all');

    const renameInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (renamingSessionId && renameInputRef.current) {
            renameInputRef.current.focus();
            renameInputRef.current.select();
        }
    }, [renamingSessionId]);

    // Voice catalog state and loader (single dynamic list)
    const [voices, setVoices] = useState<string[]>(DEFAULT_VOICES);
    const canSelectTools = queryMode === 'tools' && !isSettingsSyncing;
    const canUploadDocs = queryMode !== 'tools'; // Changed logic to be more permissive

    useEffect(() => {
        const controller = new AbortController();
        const loadVoices = async () => {
            try {
                const userId = storage.getCurrentUser() || '';
                if (!userId) return;
                const res = await getVoicesCatalog(userId, controller.signal);
                const fetched = res.available_voices || [];
                if (fetched.length > 0) setVoices(fetched);
            } catch (e) {
                // silently fall back to defaults
                console.warn('Failed to load voices catalog, using defaults');
            }
        };
        loadVoices();
        return () => controller.abort();
    }, []);


    const handleStartRename = (session: Session) => {
        setRenamingSessionId(session.id);
        setSessionName(session.name);
    };

    const handleFinishRename = () => {
        if (renamingSessionId) {
            onRenameSession(renamingSessionId, sessionName);
            setRenamingSessionId(null);
        }
    };

    const handleRenameKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter') {
            handleFinishRename();
        } else if (e.key === 'Escape') {
            setRenamingSessionId(null);
        }
    };

    return (
        <aside className={`w-80 flex-shrink-0 bg-slate-900/30 backdrop-blur-2xl border-r border-slate-500/30 flex flex-col fixed inset-y-0 left-0 z-40 transition-transform duration-300 ease-in-out ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
            {/* Header */}
            <div className="flex items-center justify-between p-4 flex-shrink-0">
                <h2 className="text-xl font-bold text-slate-200">Menu</h2>
                <button
                    onClick={onClose}
                    className="p-1.5 text-slate-300 hover:text-white hover:bg-white/10 rounded-md transition-colors lg:hidden"
                    aria-label="Close sidebar"
                >
                    <CloseIcon className="w-5 h-5" />
                </button>
            </div>

            {/* Divider */}
            <div className="border-t border-slate-500/30 flex-shrink-0 mx-4"></div>

            {/* Scrollable Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-8">
                {/* Sessions */}
                <div>
                    <div className="flex items-center justify-between mb-3">
                        <h2 className="text-lg font-semibold text-slate-200">Sessions</h2>
                        <button
                            onClick={() => { onNewSession(); }}
                            className="p-1.5 text-slate-300 hover:text-white hover:bg-white/10 rounded-md transition-colors"
                            title="New Session"
                        >
                            <PlusIcon className="w-5 h-5" />
                        </button>
                    </div>
                    <div className="max-h-[280px] overflow-y-auto space-y-1.5 scrollbar-thin scrollbar-thumb-slate-600 scrollbar-track-transparent">
                        {sessions.map(session => (
                            <div key={session.id} className="relative group">
                                <button
                                    onClick={() => {
                                        if (renamingSessionId !== session.id) {
                                            onSelectSession(session.id);
                                            // Only close sidebar on mobile (lg breakpoint is 1024px)
                                            if (window.innerWidth < 1024) {
                                                onClose();
                                            }
                                        }
                                    }}
                                    className={`w-full text-left flex items-center p-2 rounded-lg transition-colors ${session.id === activeSessionId
                                        ? 'bg-sky-500/30 text-sky-300'
                                        : 'text-slate-300 hover:bg-white/10 hover:text-white'
                                        }`}
                                >
                                    <ChatIcon className="w-4 h-4 mr-3 flex-shrink-0" />
                                    {renamingSessionId === session.id ? (
                                        <input
                                            ref={renameInputRef}
                                            type="text"
                                            value={sessionName}
                                            onChange={(e) => setSessionName(e.target.value)}
                                            onBlur={handleFinishRename}
                                            onKeyDown={handleRenameKeyDown}
                                            className="flex-1 text-sm bg-slate-800/50 rounded px-1 py-0 border border-sky-500 focus:outline-none w-0"
                                        />
                                    ) : (
                                        <span className="flex-1 text-sm truncate">{session.name}</span>
                                    )}
                                </button>
                                {renamingSessionId !== session.id && (
                                    <div className="absolute right-1 top-1/2 -translate-y-1/2 flex items-center opacity-0 group-hover:opacity-100 transition-opacity duration-200 bg-slate-800/80 rounded-md">
                                        <button
                                            onClick={() => handleStartRename(session)}
                                            className="p-1.5 text-slate-400 hover:text-white rounded-md"
                                            title="Rename session"
                                        >
                                            <EditIcon className="w-4 h-4" />
                                        </button>
                                        <button
                                            onClick={() => onDeleteSession(session.id)}
                                            className="p-1.5 text-slate-400 hover:text-red-400 rounded-md"
                                            title="Delete session"
                                        >
                                            <TrashIcon className="w-4 h-4" />
                                        </button>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>

                {/* Settings */}
                <div className="pt-2">
                    <h2 className="text-lg font-bold text-slate-200 mb-4">Settings</h2>
                    <div className="space-y-6">
                        {/* Model Selector - Collapsible with provider tabs */}
                        <ModelSelector
                            currentModel={currentModel}
                            onModelChange={onModelChange}
                            availableModels={availableModelsLabeled || []}
                        />
                        {/* Voice Selector - Collapsible drill-down picker */}
                        <VoiceSelector
                            currentVoice={currentVoice}
                            onVoiceChange={onVoiceChange}
                            availableVoices={availableVoicesLabeled || []}
                        />

                        {/* Tools Selector - Categorized with Docker/Web/Local tabs */}
                        <ToolsSelector
                            mcpToolsCatalog={mcpToolsCatalog}
                            selectedMcpTools={selectedMcpTools}
                            onSelectedMcpToolsChange={onSelectedMcpToolsChange}
                            mcpStdioCatalog={mcpStdioCatalog}
                            selectedMcpStdio={selectedMcpStdio}
                            onSelectedMcpStdioChange={onSelectedMcpStdioChange}
                            canSelectTools={canSelectTools}
                            isSettingsSyncing={isSettingsSyncing}
                            onShowConfirmation={onShowConfirmation}
                        />
                    </div>
                </div>

                {/* Knowledge Base */}
                <div>
                    <h2 className="text-lg font-semibold text-slate-200 mb-3">Knowledge Base</h2>
                    <p className="text-sm text-slate-400 mb-4">Add documents to provide context for the AI assistant.</p>
                    {/* Upload button with hover tooltip when disabled */}
                    <div className={`relative ${!canUploadDocs ? 'group' : ''}`}>
                        <label className={`flex items-center justify-center w-full h-24 px-4 transition bg-slate-800/50 border-2 border-slate-600 border-dashed rounded-lg appearance-none ${canUploadDocs ? 'cursor-pointer hover:border-sky-500 focus:outline-none' : 'cursor-not-allowed opacity-50'}`}>
                            <div className="flex flex-col items-center space-y-2">
                                <UploadIcon className="w-6 h-6 text-slate-400" />
                                <span className="font-medium text-slate-400 text-sm">
                                    {canUploadDocs ? 'Drop files to Attach' : 'Switch to Chat mode'}
                                </span>
                            </div>
                            <input
                                type="file"
                                className="hidden"
                                onChange={(e) => {
                                    if (canUploadDocs) {
                                        onFileChange(e);
                                    }
                                }}
                                disabled={!canUploadDocs}
                            />
                        </label>
                        {!canUploadDocs && (
                            <div className="pointer-events-none absolute -bottom-10 left-0 bg-gray-900/90 text-white text-xs px-2 py-1 rounded-md shadow-md opacity-0 group-hover:opacity-100 backdrop-blur-sm">
                                Switch to Chat mode to enable file uploads
                            </div>
                        )}
                    </div>

                    {/* File category filter tabs - subtle underline style */}
                    {uploadedFiles.length > 0 && (
                        <div className="mt-4 mb-2 flex justify-center border-b border-slate-700/50">
                            {(['all', 'user', 'admin'] as const).map((filter) => {
                                const isActive = fileFilter === filter;
                                const count = filter === 'all'
                                    ? uploadedFiles.length
                                    : filter === 'admin'
                                        ? uploadedFiles.filter(f => f.is_admin_uploaded).length
                                        : uploadedFiles.filter(f => !f.is_admin_uploaded).length;
                                const label = filter === 'all' ? 'All' : filter === 'admin' ? 'Admin' : 'Mine';

                                return (
                                    <button
                                        key={filter}
                                        onClick={() => setFileFilter(filter)}
                                        className={`relative px-3 py-1.5 text-xs transition-colors ${isActive
                                            ? 'text-sky-400'
                                            : 'text-slate-500 hover:text-slate-300'
                                            }`}
                                    >
                                        <span className="flex items-center gap-1">
                                            {label}
                                            <span className={`text-[10px] ${isActive ? 'text-sky-400/70' : 'text-slate-600'}`}>
                                                {count}
                                            </span>
                                        </span>
                                        {/* Active indicator underline */}
                                        {isActive && (
                                            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-sky-500 rounded-full" />
                                        )}
                                    </button>
                                );
                            })}
                        </div>
                    )}

                    {/* Scrollable file list with max height */}
                    <div className="mt-2 max-h-[200px] overflow-y-auto space-y-2 scrollbar-thin scrollbar-thumb-slate-600 scrollbar-track-transparent">
                        {uploadedFiles
                            .filter(file => {
                                if (fileFilter === 'all') return true;
                                if (fileFilter === 'admin') return file.is_admin_uploaded;
                                return !file.is_admin_uploaded;
                            })
                            .map((file, index) => (
                                <div key={index} className="flex items-center justify-between p-2 bg-slate-800/50 rounded-lg">
                                    <div className="flex items-center space-x-2 overflow-hidden">
                                        <DocumentIcon className="w-4 h-4 text-sky-400 flex-shrink-0" />
                                        <span className="text-sm text-slate-300 truncate" title={file.file.name}>{file.file.name}</span>
                                        {file.is_admin_uploaded && (
                                            <span className="text-[10px] bg-sky-900/50 text-sky-200 px-1 rounded border border-sky-700/50 ml-1 flex-shrink-0" title="Uploaded by Admin">
                                                Admin
                                            </span>
                                        )}
                                    </div>
                                    <div className="flex items-center space-x-2 flex-shrink-0">
                                        <StatusIcon status={file.status} />
                                        {!file.is_admin_uploaded ? (
                                            <button
                                                onClick={() => onDeleteDocument(file.file.name, file.kind)}
                                                className="text-slate-500 hover:text-red-400 transition-colors"
                                                title="Delete document"
                                            >
                                                <TrashIcon className="w-4 h-4" />
                                            </button>
                                        ) : (
                                            <div className="w-4 h-4" />
                                        )}
                                    </div>
                                </div>
                            ))}
                        {uploadedFiles.length > 0 && uploadedFiles.filter(file => {
                            if (fileFilter === 'all') return true;
                            if (fileFilter === 'admin') return file.is_admin_uploaded;
                            return !file.is_admin_uploaded;
                        }).length === 0 && (
                                <p className="text-xs text-slate-500 text-center py-2">
                                    No {fileFilter === 'admin' ? 'admin' : 'user'} files
                                </p>
                            )}
                    </div>
                </div>

                {/* Logout */}
                <div className="pt-4 border-t border-slate-500/30">
                    <button
                        onClick={onLogout}
                        className="flex items-center w-full px-4 py-2 text-sm font-medium text-slate-400 transition-colors rounded-lg hover:bg-slate-800/50 hover:text-white"
                    >
                        <LogoutIcon className="w-5 h-5 mr-3" />
                        Sign Out
                    </button>
                </div>
            </div>
        </aside >
    );
};
