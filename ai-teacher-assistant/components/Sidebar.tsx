
import React, { useState, useRef, useEffect } from 'react';
import { UploadedFile, Session } from '../types';
import { DocumentIcon, UploadIcon, SpinnerIcon, CheckIcon, ErrorIcon, PlusIcon, LogoutIcon, ChatIcon, CloseIcon, EditIcon, TrashIcon } from './icons';

interface SidebarProps {
    uploadedFiles: UploadedFile[];
    onFileChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
    sessions: Session[];
    activeSessionId: string | null;
    onNewSession: () => void;
    onSelectSession: (sessionId: string) => void;
    onRenameSession: (sessionId: string, newName: string) => void;
    onDeleteSession: (sessionId: string) => void;
    onLogout: () => void;
    isSidebarOpen: boolean;
    onClose: () => void;
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

export const Sidebar: React.FC<SidebarProps> = ({ 
    uploadedFiles, 
    onFileChange, 
    sessions, 
    activeSessionId, 
    onNewSession, 
    onSelectSession, 
    onRenameSession,
    onDeleteSession,
    onLogout,
    isSidebarOpen,
    onClose
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
        <aside className={`w-72 flex-shrink-0 bg-gray-800 p-4 border-r border-gray-700 flex flex-col fixed inset-y-0 left-0 z-40 transition-transform duration-300 ease-in-out ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
            <div className="flex-1 flex flex-col overflow-y-auto">
                 <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-gray-200">Menu</h2>
                    <button 
                        onClick={onClose}
                        className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded-md transition-colors"
                        aria-label="Close sidebar"
                    >
                        <CloseIcon className="w-5 h-5" />
                    </button>
                </div>

                <div className="mb-4">
                    <div className="flex items-center justify-between mb-3">
                        <h2 className="text-lg font-semibold text-gray-200">Sessions</h2>
                        <button 
                            onClick={() => {
                                onNewSession();
                                onClose();
                            }}
                            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded-md transition-colors"
                            title="New Session"
                        >
                            <PlusIcon className="w-5 h-5" />
                        </button>
                    </div>
                    <div className="pr-1 space-y-1.5">
                        {sessions.map(session => (
                            <div key={session.id} className="relative group">
                                <button
                                    onClick={() => {
                                        if (renamingSessionId !== session.id) {
                                            onSelectSession(session.id);
                                            onClose();
                                        }
                                    }}
                                    className={`w-full text-left flex items-center p-2 rounded-md transition-colors ${
                                        session.id === activeSessionId
                                            ? 'bg-sky-600/50 text-white'
                                            : 'text-gray-400 hover:bg-gray-700/50 hover:text-gray-200'
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
                                            className="flex-1 text-sm bg-gray-900/80 rounded px-1 py-0 border border-sky-500 focus:outline-none w-0"
                                        />
                                    ) : (
                                        <span className="flex-1 text-sm truncate">{session.name}</span>
                                    )}
                                </button>
                                {renamingSessionId !== session.id && (
                                    <div className="absolute right-1 top-1/2 -translate-y-1/2 flex items-center opacity-0 group-hover:opacity-100 transition-opacity duration-200 bg-gray-700/50 rounded-md">
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

                <div className="border-t border-gray-700 pt-4 mb-4">
                    <h2 className="text-lg font-semibold text-gray-200 mb-3">Knowledge Base</h2>
                    <p className="text-sm text-gray-400 mb-4">Add documents to provide context for the AI assistant.</p>
                    <label htmlFor="file-upload" className="w-full cursor-pointer bg-sky-600 hover:bg-sky-700 text-white font-bold py-2 px-4 rounded-lg inline-flex items-center justify-center transition-colors">
                        <UploadIcon className="w-5 h-5 mr-2" />
                        <span>Upload Document</span>
                    </label>
                    <input id="file-upload" type="file" className="hidden" onChange={onFileChange} multiple />
                </div>
                
                <div>
                    <h3 className="text-md font-semibold text-gray-300 mb-2">Uploaded Files</h3>
                    {uploadedFiles.length > 0 ? (
                        <ul className="space-y-2">
                            {uploadedFiles.map((upload) => (
                                <li key={upload.id} className="flex items-center p-2 rounded-md bg-gray-700/50">
                                    <DocumentIcon className="w-5 h-5 mr-3 text-sky-400 flex-shrink-0" />
                                    <span className="flex-1 text-sm text-gray-300 truncate" title={upload.file.name}>{upload.file.name}</span>
                                    <div className="ml-2">
                                        <StatusIcon status={upload.status} />
                                    </div>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <div className="text-center text-gray-500 p-4 border-2 border-dashed border-gray-600 rounded-lg">
                            <p>No documents uploaded.</p>
                        </div>
                    )}
                </div>
            </div>

            <div className="mt-auto flex-shrink-0">
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