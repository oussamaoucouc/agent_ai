import React, { useState, useRef, useEffect } from 'react';
import { UploadedFile, Session, TTSVoice } from '../types';
import { DocumentIcon, UploadIcon, SpinnerIcon, CheckIcon, ErrorIcon, PlusIcon, LogoutIcon, ChatIcon, CloseIcon, EditIcon, TrashIcon, CubeIcon, SpeakerIcon } from './icons';

interface SidebarProps {
    uploadedFiles: UploadedFile[];
    onFileChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
    onDeleteDocument: (filename: string) => void;
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

const femaleVoiceOptions: { id: TTSVoice }[] = [
    { id: TTSVoice.AF_BELLA }, { id: TTSVoice.AF_NICOLE }, { id: TTSVoice.AF_SARAH },
    { id: TTSVoice.AF_SKY }, { id: TTSVoice.BF_EMMA }, { id: TTSVoice.BF_ISABELLA },
];
const maleVoiceOptions: { id: TTSVoice }[] = [
    { id: TTSVoice.AM_ADAM }, { id: TTSVoice.AM_MICHAEL }, { id: TTSVoice.BM_GEORGE }, { id: TTSVoice.BM_LEWIS },
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
    onVoiceChange
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
                                    <option value="granite4:tiny-h o">granite4:tiny-h</option>
                                    <option value="qwen3:1.7b">qwen3:1.7b</option>
                                    <option value="qwen2.5:3b">qwen2.5:3b</option>
                                    <option value="phi4-mini:3.8b ">phi4-mini:3.8b </option>
                                    <option value="ai_teacher_qwen">ai_teacher_qwen</option>              
                                </select>
                                <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-gray-400">
                                    <svg className="fill-current h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z"/></svg>
                                </div>
                            </div>
                            <p className="mt-2 text-xs text-gray-500">
                                Choose the AI model to power your assistant. Pro is more capable, while Flash is faster.
                            </p>
                        </div>
                        <div>
                             <h3 className="text-sm font-medium text-gray-400 mb-2 flex items-center"><SpeakerIcon className="w-4 h-4 mr-2" />Voice</h3>
                             <h4 className="text-xs font-semibold text-gray-500 mb-2">Female Voices</h4>
                             <div className="grid grid-cols-3 gap-2">
                                {femaleVoiceOptions.map(voice => (
                                    <button
                                        key={voice.id}
                                        onClick={() => onVoiceChange(voice.id)}
                                        className={`px-2 py-1.5 text-xs font-mono rounded-lg transition-colors border-2 focus:outline-none focus:border-sky-500 ${
                                            currentVoice === voice.id ? 'bg-sky-500 text-white font-bold border-sky-500' : 'bg-slate-800 hover:bg-slate-700 text-gray-300 border-transparent'
                                        }`}
                                    >
                                        {voice.id.replace('af_', 'af-').replace('bf_', 'bf-')}
                                    </button>
                                ))}
                            </div>
                            <h4 className="text-xs font-semibold text-gray-500 mt-3 mb-2">Male Voices</h4>
                             <div className="grid grid-cols-3 gap-2">
                                {maleVoiceOptions.map(voice => (
                                    <button
                                        key={voice.id}
                                        onClick={() => onVoiceChange(voice.id)}
                                        className={`px-2 py-1.5 text-xs font-mono rounded-lg transition-colors border-2 focus:outline-none focus:border-sky-500 ${
                                            currentVoice === voice.id ? 'bg-sky-500 text-white font-bold border-sky-500' : 'bg-slate-800 hover:bg-slate-700 text-gray-300 border-transparent'
                                        }`}
                                    >
                                        {voice.id.replace('am_', 'am-').replace('bm_', 'bm-')}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Knowledge Base */}
                <div>
                    <h2 className="text-lg font-semibold text-gray-200 mb-3">Knowledge Base</h2>
                    <p className="text-sm text-gray-400 mb-4">Add documents to provide context for the AI assistant.</p>
                    <label htmlFor="file-upload" className="w-full cursor-pointer bg-sky-600 hover:bg-sky-700 text-white font-bold py-2 px-4 rounded-lg inline-flex items-center justify-center transition-colors">
                        <UploadIcon className="w-5 h-5 mr-2" />
                        <span>Upload Document</span>
                    </label>
                    <input id="file-upload" type="file" className="hidden" onChange={onFileChange} multiple />
                
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
                                            onClick={() => onDeleteDocument(upload.file.name)}
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