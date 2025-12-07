import React, { useState, useRef, useEffect } from 'react';
import { UploadedFile, Session, TTSVoice, QueryMode } from '../types';
import * as storage from '../services/storageService';
import { getVoicesCatalog } from '../services/apiService';
import { McpToolItem } from '../types';
import { CustomDropdown } from './CustomDropdown';
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
    const [selectedProvider, setSelectedProvider] = useState<string>('');

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

    // Docker MCP Gateway detection - checks if a tool URL contains "mcp-gateway"
    const isDockerGateway = (tool: McpToolItem): boolean => {
        return tool.url.toLowerCase().includes('mcp-gateway');
    };

    // Check if Docker gateway is currently selected
    const isDockerGatewayActive = mcpToolsCatalog.some(
        tool => isDockerGateway(tool) && selectedMcpTools.includes(tool.label)
    );

    const toggleMcpTool = (label: string) => {
        if (!canSelectTools) return;

        const tool = mcpToolsCatalog.find(t => t.label === label);
        const isSelectingGateway = tool && isDockerGateway(tool);
        const isAlreadySelected = selectedMcpTools.includes(label);

        // Case 1: Deselecting Docker gateway - just deselect normally
        if (isSelectingGateway && isAlreadySelected) {
            onSelectedMcpToolsChange([]);
            return;
        }

        // Case 2: Selecting Docker gateway - show confirmation first
        if (isSelectingGateway && !isAlreadySelected) {
            if (onShowConfirmation) {
                onShowConfirmation(
                    'Docker MCP Gateway Mode',
                    'Selecting Docker Gateway enables exclusive mode. All other Web Tools and Local Tools will be cleared. Do you want to continue?',
                    () => {
                        // On confirm: select only Docker gateway and clear Local Tools
                        onSelectedMcpToolsChange([label]);
                        onSelectedMcpStdioChange([]);
                    }
                );
            } else {
                // Fallback if no confirmation handler
                onSelectedMcpToolsChange([label]);
                onSelectedMcpStdioChange([]);
            }
            return;
        }

        // Case 3: Docker gateway is active and user tries to select another tool
        if (isDockerGatewayActive && !isSelectingGateway) {
            // Don't allow - gateway is exclusive
            return;
        }

        // Case 4: Normal toggle (no gateway involved)
        const nextLabels = isAlreadySelected
            ? selectedMcpTools.filter(l => l !== label)
            : [...selectedMcpTools, label];
        onSelectedMcpToolsChange(nextLabels);
    };

    const toggleMcpStdio = (cmd: string) => {
        // Don't allow stdio selection if Docker gateway is active
        if (!canSelectTools || isDockerGatewayActive) return;

        const next = selectedMcpStdio.includes(cmd)
            ? selectedMcpStdio.filter(c => c !== cmd)
            : [...selectedMcpStdio, cmd];
        onSelectedMcpStdioChange(next);
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

    // Group models by provider and infer provider if missing
    const modelsByProvider = (availableModelsLabeled || []).reduce((acc, m) => {
        // Infer provider from model ID if not set
        let provider = m.provider;
        if (!provider) {
            if (m.id.startsWith('openrouter/')) {
                provider = 'openrouter';
            } else if (m.id.startsWith('gemini/')) {
                provider = 'gemini';
            } else if (m.id.startsWith('gpt/')) {
                provider = 'openai';
            } else if (m.id.startsWith('openai/')) {
                provider = 'openai';
            } else {
                provider = 'ollama';
            }
        }
        if (!acc[provider]) acc[provider] = [];
        acc[provider].push(m);
        return acc;
    }, {} as Record<string, Array<{ label: string; id: string; provider?: string }>>);

    const providers = Object.keys(modelsByProvider);

    // Set initial selected provider when models load
    useEffect(() => {
        if (providers.length > 0 && !selectedProvider) {
            // Try to find provider of current model
            let initialProvider = providers[0];
            for (const [prov, models] of Object.entries(modelsByProvider) as [string, Array<{ label: string; id: string; provider?: string }>][]) {
                if (models.some(m => m.id === currentModel)) {
                    initialProvider = prov;
                    break;
                }
            }
            setSelectedProvider(initialProvider);
        }
    }, [availableModelsLabeled, currentModel]);

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
                    <div className="space-y-1.5">
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
                        <div>
                            <h3 className="text-sm font-medium text-slate-400 mb-2 flex items-center"><CubeIcon className="w-4 h-4 mr-2" />AI Model</h3>

                            {/* Provider Selection */}
                            {providers.length > 0 && (
                                <div className="mb-3">
                                    <CustomDropdown
                                        label="Provider"
                                        options={providers}
                                        value={selectedProvider}
                                        onChange={setSelectedProvider}
                                    />
                                </div>
                            )}

                            <div className="grid grid-cols-2 gap-2">
                                {(modelsByProvider[selectedProvider] || []).map((m) => (
                                    <button
                                        key={m.id}
                                        onClick={() => onModelChange(m.id)}
                                        title={m.label}
                                        className={`w-full text-center truncate px-2 py-1.5 text-xs rounded-lg transition-colors border focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-900 focus:ring-sky-500 ${currentModel === m.id ? 'bg-sky-500 text-white font-bold border-sky-500' : 'bg-slate-700/50 hover:bg-slate-700 text-slate-300 border-slate-600'
                                            }`}
                                    >
                                        {m.label}
                                    </button>
                                ))}
                            </div>
                            {(!availableModelsLabeled || availableModelsLabeled.length === 0) && (
                                <p className="mt-2 text-xs text-slate-500">No models configured.</p>
                            )}
                            <p className="mt-2 text-xs text-slate-500">
                                Choose the AI model to power your assistant.
                            </p>
                        </div>
                        {/* Voices at top */}
                        <div>
                            <h3 className="text-sm font-medium text-slate-400 mb-2 flex items-center"><SpeakerIcon className="w-4 h-4 mr-2" />Voices</h3>
                            <div className="grid grid-cols-3 gap-2">
                                {(availableVoicesLabeled || []).map(v => (
                                    <button
                                        key={v.id}
                                        onClick={() => onVoiceChange(v.id as TTSVoice)}
                                        className={`px-2 py-1.5 text-xs rounded-lg transition-colors border focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-900 focus:ring-sky-500 ${currentVoice === (v.id as TTSVoice) ? 'bg-sky-500 text-white font-bold border-sky-500' : 'bg-slate-700/50 hover:bg-slate-700 text-slate-300 border-slate-600'
                                            }`}
                                    >
                                        {v.label}
                                    </button>
                                ))}
                            </div>
                            {(!availableVoicesLabeled || availableVoicesLabeled.length === 0) && (
                                <p className="mt-2 text-xs text-slate-500">No voices configured.</p>
                            )}
                        </div>
                        {/* Tools multi-select below Voices */}
                        <div className={`transition-opacity duration-200 ${isSettingsSyncing ? 'opacity-50 pointer-events-none' : ''}`}>
                            {/* Autonomous Mode - Docker Gateway Section */}
                            {mcpToolsCatalog.some(isDockerGateway) && (
                                <>
                                    <div className="flex items-center gap-2 mb-2">
                                        <h3 className="text-sm font-medium text-orange-400">🤖 Autonomous Mode</h3>
                                        {isDockerGatewayActive && (
                                            <span className="text-[10px] bg-orange-500/20 text-orange-400 px-2 py-0.5 rounded-full border border-orange-500/30 animate-pulse">
                                                Active
                                            </span>
                                        )}
                                    </div>
                                    <div className="grid grid-cols-1 gap-2 mb-3">
                                        {mcpToolsCatalog.filter(isDockerGateway).map(tool => {
                                            const isSelected = selectedMcpTools.includes(tool.label);
                                            return (
                                                <button
                                                    key={tool.label}
                                                    onClick={() => toggleMcpTool(tool.label)}
                                                    disabled={!canSelectTools}
                                                    className={`px-3 py-2 text-xs rounded-lg transition-all duration-200 border focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-900 focus:ring-orange-500 ${isSelected
                                                        ? 'bg-gradient-to-r from-orange-500 to-amber-500 text-white font-bold border-orange-400 shadow-lg shadow-orange-500/30'
                                                        : canSelectTools
                                                            ? 'bg-orange-500/10 hover:bg-orange-500/20 text-orange-300 border-orange-500/30 hover:border-orange-500/60'
                                                            : 'bg-slate-800/50 opacity-50 cursor-not-allowed text-slate-300 border-slate-600'
                                                        }`}
                                                    title="Enable full autonomous mode with all Docker tools"
                                                >
                                                    <span className="flex items-center justify-center gap-2">
                                                        <span>⚡</span>
                                                        <span>{tool.label}</span>
                                                    </span>
                                                </button>
                                            );
                                        })}
                                    </div>
                                    <p className="text-xs text-orange-400/60 mb-4 italic">
                                        {isDockerGatewayActive
                                            ? 'All Docker tools active. Other tools disabled.'
                                            : 'Enables all containerized tools in one click.'}
                                    </p>
                                    <div className="border-t border-slate-700/50 my-3"></div>
                                </>
                            )}

                            {/* Regular Web Tools Section */}
                            <h3 className="text-sm font-medium text-slate-400 mb-2">Web Tools</h3>
                            <div className={`relative ${!canSelectTools ? 'group' : ''}`}>
                                <div className="grid grid-cols-2 gap-2">
                                    {mcpToolsCatalog.filter(tool => !isDockerGateway(tool)).map(tool => {
                                        const isSelected = selectedMcpTools.includes(tool.label);
                                        const isDisabled = !canSelectTools || isDockerGatewayActive;

                                        return (
                                            <button
                                                key={tool.label}
                                                onClick={() => toggleMcpTool(tool.label)}
                                                disabled={isDisabled}
                                                className={`px-2 py-1.5 text-xs rounded-lg transition-colors border focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-900 focus:ring-sky-500 ${isSelected
                                                    ? 'bg-sky-500 text-white font-bold border-sky-500'
                                                    : isDisabled
                                                        ? 'bg-slate-800/50 opacity-50 cursor-not-allowed text-slate-300 border-slate-600'
                                                        : 'bg-slate-700/50 hover:bg-slate-700 text-slate-300 border-slate-600'
                                                    }`}
                                                title={isDockerGatewayActive ? 'Disabled: Autonomous mode is active' : tool.label}
                                            >
                                                {tool.label}
                                            </button>
                                        );
                                    })}
                                </div>
                                {!canSelectTools && (
                                    <div className="pointer-events-none absolute -bottom-10 left-0 bg-gray-900/90 text-white text-xs px-2 py-1 rounded-md shadow-md opacity-0 group-hover:opacity-100 backdrop-blur-sm">
                                        {isSettingsSyncing ? 'Loading...' : 'Switch to Tools mode to enable tool selection'}
                                    </div>
                                )}
                            </div>
                            <p className="mt-2 text-xs text-slate-500">
                                {isDockerGatewayActive
                                    ? 'Disabled while Autonomous mode is active.'
                                    : canSelectTools
                                        ? 'Select individual tools to use.'
                                        : 'Switch to Tools mode to select tools.'}
                            </p>
                            <h3 className="text-sm font-medium text-slate-400 mb-2">Local Tools</h3>
                            <div className={`relative ${(!canSelectTools || isDockerGatewayActive) ? 'group' : ''}`}>
                                <div className="grid grid-cols-2 gap-2">
                                    {mcpStdioCatalog.map(item => {
                                        const isDisabled = !canSelectTools || isDockerGatewayActive;
                                        return (
                                            <button
                                                key={item.command}
                                                onClick={() => toggleMcpStdio(item.command)}
                                                disabled={isDisabled}
                                                className={`px-2 py-1.5 text-xs rounded-lg transition-colors border focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-900 focus:ring-sky-500 ${selectedMcpStdio.includes(item.command)
                                                    ? 'bg-sky-500 text-white font-bold border-sky-500'
                                                    : isDisabled
                                                        ? 'bg-slate-800/50 opacity-50 cursor-not-allowed text-slate-300 border-slate-600'
                                                        : 'bg-slate-700/50 hover:bg-slate-700 text-slate-300 border-slate-600'
                                                    }`}
                                                title={isDockerGatewayActive ? 'Disabled: Autonomous mode is active' : item.label}
                                            >
                                                {item.label}
                                            </button>
                                        );
                                    })}
                                </div>
                                {(!canSelectTools || isDockerGatewayActive) && (
                                    <div className="pointer-events-none absolute -bottom-10 left-0 bg-gray-900/90 text-white text-xs px-2 py-1 rounded-md shadow-md opacity-0 group-hover:opacity-100 backdrop-blur-sm">
                                        {isSettingsSyncing ? 'Loading...' : isDockerGatewayActive ? 'Local Tools disabled in Autonomous mode' : 'Switch to Tools mode to enable stdio selection'}
                                    </div>
                                )}
                            </div>
                            <p className="mt-2 text-xs text-slate-500">
                                {isDockerGatewayActive
                                    ? 'Local Tools are disabled in Autonomous mode.'
                                    : 'Local tools run locally configured by the administrator.'}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Knowledge Base */}
                <div>
                    <h2 className="text-lg font-semibold text-slate-200 mb-3">Knowledge Base</h2>
                    <p className="text-sm text-slate-400 mb-4">Add documents to provide context for the AI assistant.</p>
                    {/* Upload button with hover tooltip when disabled */}
                    <div className={`relative ${!canUploadDocs ? 'group' : ''}`}>
                        <label className={`flex items-center justify-center w-full h-32 px-4 transition bg-slate-800/50 border-2 border-slate-600 border-dashed rounded-lg appearance-none ${canUploadDocs ? 'cursor-pointer hover:border-sky-500 focus:outline-none' : 'cursor-not-allowed opacity-50'}`}>
                            <div className="flex flex-col items-center space-y-2">
                                <UploadIcon className="w-8 h-8 text-slate-400" />
                                <span className="font-medium text-slate-400">
                                    {canUploadDocs ? 'Drop files to Attach' : 'Switch to Chat mode to upload'}
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

                    <div className="mt-4 space-y-2">
                        {uploadedFiles.map((file, index) => (
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
