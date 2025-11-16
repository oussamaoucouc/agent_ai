import React, { useState, useRef, useEffect } from 'react';
import { UploadedFile, Session, TTSVoice, QueryMode } from '../types';
import * as storage from '../services/storageService';
import { getVoicesCatalog, getMcpToolsCatalog, setMcpTools, getSessionSettings } from '../services/apiService';
import { McpToolItem } from '../types';
import { DocumentIcon, UploadIcon, SpinnerIcon, CheckIcon, ErrorIcon, PlusIcon, LogoutIcon, ChatIcon, CloseIcon, EditIcon, TrashIcon, CubeIcon, SpeakerIcon } from './icons';

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
    availableModels?: string[];
    queryMode: QueryMode;
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

const DEFAULT_VOICES: string[] = [
    TTSVoice.AF_BELLA,
    TTSVoice.AF_NICOLE,
    TTSVoice.AF_SARAH,
    TTSVoice.AF_SKY,
    TTSVoice.BF_EMMA,
    TTSVoice.BF_ISABELLA,
    TTSVoice.AM_ADAM,
    TTSVoice.AM_MICHAEL,
    TTSVoice.BM_GEORGE,
    TTSVoice.BM_LEWIS,
];


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
    availableModels,
    queryMode
}) => {
    const [renamingSessionId, setRenamingSessionId] = useState<string | null>(null);
    const [sessionName, setSessionName] = useState('');
    
    const renameInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (renamingSessionId && renameInputRef.current) {
            renameInputRef.current.focus();
            renameInputRef.current.select();
        }
    }, [renamingSessionId]);

    // Voice catalog state and loader (single dynamic list)
    const [voices, setVoices] = useState<string[]>(DEFAULT_VOICES);

    // MCP tools catalog and per-user selection
    const [mcpTools, setMcpToolsCatalog] = useState<McpToolItem[]>([]);
    const [selectedMcpToolLabels, setSelectedMcpToolLabels] = useState<string[]>([]);
    const canSelectTools = queryMode === 'tools';
    const canUploadDocs = queryMode === 'direct';

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
        const loadMcpTools = async () => {
            try {
                const userId = storage.getCurrentUser() || '';
                if (!userId) return;
                const res = await getMcpToolsCatalog(userId, controller.signal);
                const items = Array.isArray(res.tools) ? res.tools : [];
                setMcpToolsCatalog(items);
            } catch (e) {
                console.warn('Failed to load MCP tools catalog');
            }
        };
        loadVoices();
        loadMcpTools();
        return () => controller.abort();
    }, []);

    // Load currently selected MCP tools for this user/session
    useEffect(() => {
        const controller = new AbortController();
        const loadSessionSettings = async () => {
            try {
                const userId = storage.getCurrentUser() || '';
                const sessionId = activeSessionId || storage.getActiveSessionId() || '';
                if (!userId || !sessionId) return;
                const res = await getSessionSettings(userId, sessionId, controller.signal);
                const urls = Array.isArray(res.mcp_tools_urls) ? res.mcp_tools_urls : [];
                // Map URLs to labels for display selection state
                const byUrl = new Map((mcpTools || []).map(t => [t.url, t.label]));
                const labels = urls.map(u => byUrl.get(u) || u);
                setSelectedMcpToolLabels(labels);
            } catch (e) {
                // ignore
            }
        };
        loadSessionSettings();
        return () => controller.abort();
        // re-run when session changes or catalog fetched
    }, [activeSessionId, mcpTools.length]);

    const toggleMcpTool = async (label: string) => {
        if (!canSelectTools) return; // gate selection unless Tools mode is active
        const userId = storage.getCurrentUser() || '';
        const sessionId = activeSessionId || storage.getActiveSessionId() || '';
        if (!userId || !sessionId) return;
        const nextLabels = selectedMcpToolLabels.includes(label)
            ? selectedMcpToolLabels.filter(l => l !== label)
            : [...selectedMcpToolLabels, label];
        setSelectedMcpToolLabels(nextLabels);
        try {
            await setMcpTools({ user_id: userId, session_id: sessionId, tool_labels: nextLabels });
        } catch (e) {
            console.warn('Failed to persist MCP tools selection');
        }
    };


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
        <aside className={`w-72 flex-shrink-0 bg-slate-900 p-0 border-r border-slate-800 flex flex-col fixed inset-y-0 left-0 z-40 transition-transform duration-300 ease-in-out ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
            {/* Header */}
            <div className="flex items-center justify-between p-4 flex-shrink-0">
                <h2 className="text-xl font-bold text-gray-200">Menu</h2>
                <button 
                    onClick={onClose}
                    className="p-1.5 text-gray-400 hover:text-white hover:bg-slate-700 rounded-md transition-colors"
                    aria-label="Close sidebar"
                >
                    <CloseIcon className="w-5 h-5" />
                </button>
            </div>
             
             {/* Divider */}
             <div className="border-t border-slate-700 flex-shrink-0 mx-4"></div>

             {/* Scrollable Content */}
             <div className="flex-1 overflow-y-auto p-4 space-y-8">
                {/* Sessions */}
                <div>
                    <div className="flex items-center justify-between mb-3">
                        <h2 className="text-lg font-semibold text-gray-200">Sessions</h2>
                        <button 
                            onClick={() => { onNewSession(); }}
                            className="p-1.5 text-gray-400 hover:text-white hover:bg-slate-700 rounded-md transition-colors"
                            title="New Session"
                        >
                            <PlusIcon className="w-5 h-5" />
                        </button>
                    </div>
                    <div className="space-y-1.5">
                        {sessions.map(session => (
                            <div key={session.id} className="relative group">
                                <button
                                    onClick={() => {
                                        if (renamingSessionId !== session.id) {
                                            onSelectSession(session.id);
                                            onClose();
                                        }
                                    }}
                                    className={`w-full text-left flex items-center p-2 rounded-lg transition-colors ${
                                        session.id === activeSessionId
                                            ? 'bg-sky-500/20 text-sky-300'
                                            : 'text-gray-400 hover:bg-slate-700/50 hover:text-gray-200'
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
                                            className="flex-1 text-sm bg-slate-800 rounded px-1 py-0 border border-sky-500 focus:outline-none w-0"
                                        />
                                    ) : (
                                        <span className="flex-1 text-sm truncate">{session.name}</span>
                                    )}
                                </button>
                                {renamingSessionId !== session.id && (
                                    <div className="absolute right-1 top-1/2 -translate-y-1/2 flex items-center opacity-0 group-hover:opacity-100 transition-opacity duration-200 bg-slate-700/50 rounded-md">
                                        <button
                                            onClick={() => handleStartRename(session)}
                                            className="p-1.5 text-gray-400 hover:text-white rounded-md"
                                            title="Rename session"
                                        >
                                            <EditIcon className="w-4 h-4" />
                                        </button>
                                        <button
                                            onClick={() => onDeleteSession(session.id)}
                                            className="p-1.5 text-gray-400 hover:text-red-400 rounded-md"
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
                    <h2 className="text-lg font-bold text-gray-200 mb-4">Settings</h2>
                    <div className="space-y-6">
                        <div>
                            <h3 className="text-sm font-medium text-gray-400 mb-2 flex items-center"><CubeIcon className="w-4 h-4 mr-2" />AI Model</h3>
                            <div className="relative">
                                <select
                                    value={currentModel}
                                    onChange={(e) => onModelChange(e.target.value)}
                                    className="w-full appearance-none px-3 py-2 text-sm rounded-lg transition-colors bg-slate-800 text-gray-200 border-2 border-slate-700 focus:outline-none focus:border-sky-500"
                                >
                                    {(availableModels && availableModels.length > 0 ? availableModels : [
                                        'granite4:tiny-h',
                                        'qwen3:1.7b',
                                        'qwen2.5:3b',
                                        'phi4-mini:3.8b ',
                                        'ai_assistant_qwen'
                                    ]).map((m) => (
                                        <option key={m} value={m}>{m}</option>
                                    ))}
                                </select>
                                <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-gray-400">
                                    <svg className="fill-current h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z"/></svg>
                                </div>
                            </div>
                            <p className="mt-2 text-xs text-gray-500">
                                Choose the AI model to power your assistant. Pro is more capable, while Flash is faster.
                            </p>
                        </div>
                        {/* Voices at top */}
                        <div>
                             <h3 className="text-sm font-medium text-gray-400 mb-2 flex items-center"><SpeakerIcon className="w-4 h-4 mr-2" />Voices</h3>
                             <div className="grid grid-cols-3 gap-2">
                                {voices.map(v => (
                                    <button
                                        key={v}
                                        onClick={() => onVoiceChange(v as TTSVoice)}
                                        className={`px-2 py-1.5 text-xs font-mono rounded-lg transition-colors border-2 focus:outline-none focus:border-sky-500 ${
                                            currentVoice === (v as TTSVoice) ? 'bg-sky-500 text-white font-bold border-sky-500' : 'bg-slate-800 hover:bg-slate-700 text-gray-300 border-transparent'
                                        }`}
                                    >
                                        {v
                                            .replace('af_', 'af-')
                                            .replace('bf_', 'bf-')
                                            .replace('am_', 'am-')
                                            .replace('bm_', 'bm-')}
                                    </button>
                                ))}
                             </div>
                        </div>
                        {/* Tools multi-select below Voices */}
                        <div>
                            <h3 className="text-sm font-medium text-gray-400 mb-2">Tools</h3>
                            {/* Wrap grid to enable hover tooltip when disabled */}
                            <div className={`relative ${!canSelectTools ? 'group' : ''}`}>
                              <div className="grid grid-cols-2 gap-2">
                                {mcpTools.map(tool => (
                                    <button
                                        key={tool.label}
                                        onClick={() => toggleMcpTool(tool.label)}
                                        disabled={!canSelectTools}
                                        className={`px-2 py-1.5 text-xs rounded-lg transition-colors border-2 focus:outline-none focus:border-sky-500 ${
                                            selectedMcpToolLabels.includes(tool.label)
                                                ? 'bg-sky-500 text-white font-bold border-sky-500'
                                                : `${canSelectTools ? 'bg-slate-800 hover:bg-slate-700' : 'bg-slate-800 opacity-50 cursor-not-allowed'} text-gray-300 border-transparent`
                                        }`}
                                        title={tool.url}
                                    >
                                        {tool.label}
                                    </button>
                                ))}
                              </div>
                              {!canSelectTools && (
                                <div className="pointer-events-none absolute -top-10 left-0 bg-gray-900/90 text-white text-xs px-2 py-1 rounded-md shadow-md opacity-0 group-hover:opacity-100">
                                  Switch to Tools mode to enable tool selection
                                </div>
                              )}
                            </div>
                            <p className="mt-2 text-xs text-gray-500">
                                {canSelectTools
                                    ? 'Select tools to use with the Tools agent.'
                                    : 'Switch to Tools mode to select tools.'}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Knowledge Base */}
                <div>
                    <h2 className="text-lg font-semibold text-gray-200 mb-3">Knowledge Base</h2>
                    <p className="text-sm text-gray-400 mb-4">Add documents to provide context for the AI assistant.</p>
                    {/* Upload button with hover tooltip when disabled */}
                    <div className={`relative ${!canUploadDocs ? 'group' : ''}`}>
                      <label
                          htmlFor="file-upload"
                          className={`w-full ${canUploadDocs ? 'cursor-pointer bg-sky-600 hover:bg-sky-700' : 'cursor-not-allowed bg-slate-800 opacity-50'} text-white font-bold py-2 px-4 rounded-lg inline-flex items-center justify-center transition-colors`}
                          aria-disabled={!canUploadDocs}
                      >
                          <UploadIcon className="w-5 h-5 mr-2" />
                          <span>Upload Document</span>
                      </label>
                      {!canUploadDocs && (
                        <div className="pointer-events-none absolute -top-10 left-0 bg-gray-900/90 text-white text-xs px-2 py-1 rounded-md shadow-md opacity-0 group-hover:opacity-100">
                          Switch to Document Search mode to enable uploads
                        </div>
                      )}
                    </div>
                    <input id="file-upload" type="file" accept=".pdf,.doc,.docx,.txt,.md,.csv" className="hidden" onChange={onFileChange} multiple disabled={!canUploadDocs} />
                    {!canUploadDocs && (
                        <p className="mt-2 text-xs text-gray-500">Switch to Document Search mode to Upload Document.</p>
                    )}
                
                    <h3 className="text-md font-semibold text-gray-300 mt-4 mb-2">Uploaded Files</h3>
                    {uploadedFiles.length > 0 ? (
                        <ul className="space-y-2">
                            {uploadedFiles.map((upload) => (
                                <li key={upload.id} className="group flex items-center p-2 rounded-lg bg-slate-800">
                                    <DocumentIcon className="w-5 h-5 mr-3 text-sky-400 flex-shrink-0" />
                                    <span className="flex-1 text-sm text-gray-300 truncate" title={upload.file.name}>{upload.file.name}</span>
                                    <div className="ml-2 flex items-center gap-2">
                                        <StatusIcon status={upload.status} />
                                        <button
                                            onClick={() => onDeleteDocument(upload.file.name, upload.kind)}
                                            className="p-1.5 text-gray-400 hover:text-red-400 rounded-md opacity-0 group-hover:opacity-100 transition-opacity"
                                            title="Delete document"
                                        >
                                            <TrashIcon className="w-4 h-4" />
                                        </button>
                                    </div>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <div className="text-center text-gray-500 p-4 border-2 border-dashed border-slate-700 rounded-lg">
                            <p>No documents uploaded.</p>
                        </div>
                    )}
                </div>
            </div>

            {/* Footer */}
            <div className="p-4 flex-shrink-0">
                 <div className="border-t border-slate-700 mb-4"></div>
                 <button 
                    onClick={onLogout}
                    className="w-full flex items-center justify-center p-2.5 rounded-lg text-gray-400 hover:bg-red-800/50 hover:text-red-300 transition-colors"
                 >
                    <LogoutIcon className="w-5 h-5 mr-2" />
                    <span className="font-medium">Logout</span>
                 </button>
            </div>
        </aside>
    );
};
