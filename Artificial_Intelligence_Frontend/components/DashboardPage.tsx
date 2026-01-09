import React, { useState, useMemo, useEffect } from 'react';
import { AdminUser, UploadedFile, FileSizeLimits } from '../types';
import { LogoutIcon, UserOutlineIcon, ChatIcon, FolderOpenIcon, PlusIcon, TrashIcon, SearchIcon, EditIcon, SettingsIcon, DocumentIcon, UploadIcon, SpinnerIcon, CloseIcon } from './icons';
import { CustomDropdown } from './CustomDropdown';
import { listDocuments, uploadDocument, deleteDocument, getUserFileSizeLimits, updateUserFileSizeLimits } from '../services/apiService';
import * as storage from '../services/storageService';

interface DashboardPageProps {
    users: AdminUser[];
    onLogout: () => void;
    onNavigateToAddUser: () => void;
    onNavigateToConfig: () => void;
    onDeleteUser: (userId: string) => void;
    onEditUser: (user: AdminUser) => void;
    onShowConfirmation: (title: string, message: string, onConfirm: () => void) => void;
}

const StatCard: React.FC<{ title: string; value: string | number; icon: React.ReactNode }> = ({ title, value, icon }) => (
    <div className="bg-slate-900/30 backdrop-blur-md border border-slate-500/30 rounded-xl p-6 flex items-center gap-6 transform hover:-translate-y-1 transition-transform duration-300">
        <div className="bg-white/5 p-4 rounded-full">{icon}</div>
        <div>
            <p className="text-slate-400 text-sm font-medium">{title}</p>
            <p className="text-3xl font-bold text-white">{value}</p>
        </div>
    </div>
);

const DocumentManagementModal: React.FC<{
    user: AdminUser;
    onClose: () => void;
    onShowConfirmation: (title: string, message: string, onConfirm: () => void) => void;
}> = ({ user, onClose, onShowConfirmation }) => {
    const [documents, setDocuments] = useState<UploadedFile[]>([]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);
    const fileInputRef = React.useRef<HTMLInputElement>(null);

    // File size limits state
    const [fileSizeLimits, setFileSizeLimits] = useState<FileSizeLimits>({
        pdf: 10 * 1024 * 1024,
        docx: 10 * 1024 * 1024,
        pptx: 20 * 1024 * 1024,
        images: 20 * 1024 * 1024,
        text: 5 * 1024 * 1024,
        csv: 50 * 1024 * 1024
    });
    const [limitsExpanded, setLimitsExpanded] = useState(false);
    const [savingLimits, setSavingLimits] = useState(false);
    const [limitsLoading, setLimitsLoading] = useState(true);
    const [docFilter, setDocFilter] = useState<'all' | 'user' | 'admin'>('all');

    // Clear notification after 3 seconds
    useEffect(() => {
        if (notification) {
            const timer = setTimeout(() => setNotification(null), 3000);
            return () => clearTimeout(timer);
        }
    }, [notification]);

    // Fetch documents and file size limits on mount
    useEffect(() => {
        loadDocuments();
        loadFileSizeLimits();
    }, [user.id]);

    const loadDocuments = async () => {
        try {
            setLoading(true);
            const currentUserId = storage.getCurrentUser();
            if (!currentUserId) return;
            const res = await listDocuments(currentUserId, undefined, user.id);
            // Map response to UploadedFile
            const mapped: UploadedFile[] = res.documents.map(d => ({
                id: d.filename,
                file: new File([], d.filename), // Dummy file object
                status: 'success',
                kind: d.kind,
                is_admin_uploaded: d.is_admin_uploaded,
                uploaded_by: d.uploaded_by
            }));
            setDocuments(mapped);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const loadFileSizeLimits = async () => {
        try {
            setLimitsLoading(true);
            const res = await getUserFileSizeLimits(user.id);
            setFileSizeLimits(res.file_size_limits);
        } catch (e) {
            console.error('Failed to load file size limits:', e);
        } finally {
            setLimitsLoading(false);
        }
    };

    const handleSaveLimits = async () => {
        try {
            setSavingLimits(true);
            await updateUserFileSizeLimits(user.id, fileSizeLimits);
            setNotification({ message: 'File size limits saved successfully.', type: 'success' });
        } catch (e) {
            console.error('Failed to save file size limits:', e);
            setNotification({ message: 'Failed to save file size limits.', type: 'error' });
        } finally {
            setSavingLimits(false);
        }
    };

    const formatSizeForDisplay = (bytes: number): string => {
        // Convert to MB and limit significant digits if needed, avoiding trailing zeros
        const mb = bytes / (1024 * 1024);
        return Number(mb.toFixed(2)).toString();
    };

    const parseSizeFromInput = (mbString: string): number => {
        const mb = parseFloat(mbString);
        if (isNaN(mb)) return 0;
        return Math.floor(Math.max(0, mb) * 1024 * 1024); // Store as integer bytes
    };

    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files || e.target.files.length === 0) return;
        const file = e.target.files[0];
        setUploading(true);

        // Reset file input immediately to allow re-selection of the same file if this attempt fails or is blocked
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }

        try {
            const currentUserId = storage.getCurrentUser();
            if (!currentUserId) return;

            // Check for duplicate
            const exists = documents.some(d => d.file.name === file.name);
            if (exists) {
                setNotification({ message: `File "${file.name}" already exists. Please delete it first.`, type: 'error' });
                setUploading(false);
                return;
            }

            // Optimistic update
            const newDoc: UploadedFile = {
                id: file.name,
                file: file,
                status: 'uploading',
                is_admin_uploaded: true
            };
            setDocuments(prev => [...prev, newDoc]);

            await uploadDocument({
                file,
                user_id: currentUserId, // Admin's ID
                session_id: 'admin-upload', // Dummy session ID
                target_user_id: user.id
            });

            setNotification({ message: `File "${file.name}" uploaded successfully.`, type: 'success' });

            // Refresh list to get correct metadata
            await loadDocuments();
        } catch (e: any) {
            console.error(e);
            // Extract error message from the exception if possible
            const errorMsg = e.message || `Failed to upload "${file.name}".`;
            setNotification({ message: errorMsg, type: 'error' });

            // On error, update the document status to 'error' so the user sees it failed
            // tailored to the user's request: "delete the file after the message" implies it stays there
            setDocuments(prev => prev.map(d => d.file.name === file.name ? { ...d, status: 'error' } : d));
        } finally {
            setUploading(false);
        }
    };

    const handleDelete = async (filename: string, kind?: UploadedFile['kind']) => {
        // Check if file is in error status locally
        const docToDelete = documents.find(d => d.file.name === filename);
        // If it's an error state (red icon) or uploading, we just remove locally
        const isLocalOnly = docToDelete?.status === 'error' || docToDelete?.status === 'uploading';

        onShowConfirmation(
            'Delete Document',
            `Are you sure you want to delete ${filename}?`,
            async () => {
                try {
                    const currentUserId = storage.getCurrentUser();
                    if (!currentUserId) return;

                    // Only call backend if it was a successful upload
                    if (!isLocalOnly) {
                        await deleteDocument({
                            user_id: user.id, // Target user ID
                            filename: filename,
                            kind: kind
                        });
                    }

                    setDocuments(prev => prev.filter(d => d.file.name !== filename));
                    setNotification({ message: `File "${filename}" deleted.`, type: 'success' });
                } catch (e) {
                    console.error(e);
                    setNotification({ message: "Failed to delete document", type: 'error' });
                }
            }
        );
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
            <div className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl relative">
                {/* Notification Toast */}
                {notification && (
                    <div className={`absolute top-4 left-1/2 transform -translate-x-1/2 px-4 py-2 rounded-lg shadow-lg text-sm font-medium transition-all duration-300 z-10 ${notification.type === 'success' ? 'bg-green-500/90 text-white' :
                        notification.type === 'error' ? 'bg-red-500/90 text-white' :
                            'bg-blue-500/90 text-white'
                        }`}>
                        {notification.message}
                    </div>
                )}

                <div className="flex items-center justify-between p-4 border-b border-slate-700">
                    <h3 className="text-lg font-bold text-white">Manage Documents: {user.name}</h3>
                    <button onClick={onClose} className="text-slate-400 hover:text-white">
                        <CloseIcon className="w-5 h-5" />
                    </button>
                </div>

                <div className="p-4 flex-1 overflow-y-auto">
                    {/* Upload Area */}
                    <div className="mb-6">
                        <label className={`flex flex-col items-center justify-center w-full h-32 border-2 border-slate-600 border-dashed rounded-lg bg-slate-800/50 transition-colors ${uploading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:bg-slate-800 hover:border-sky-500'}`}>
                            <div className="flex flex-col items-center justify-center pt-5 pb-6">
                                <UploadIcon className="w-8 h-8 mb-3 text-slate-400" />
                                <p className="mb-2 text-sm text-slate-400"><span className="font-semibold">Click to upload</span> or drag and drop</p>
                                <p className="text-xs text-slate-500">PDF, DOCX, PPTX, TXT, CSV, Images</p>
                            </div>
                            <input
                                ref={fileInputRef}
                                type="file"
                                className="hidden"
                                onChange={handleUpload}
                                disabled={uploading}
                            />
                        </label>
                    </div>

                    {/* File category filter tabs */}
                    {documents.length > 0 && (
                        <div className="mb-3 flex justify-center border-b border-slate-700/50">
                            {(['all', 'user', 'admin'] as const).map((filter) => {
                                const isActive = docFilter === filter;
                                const count = filter === 'all'
                                    ? documents.length
                                    : filter === 'admin'
                                        ? documents.filter(f => f.is_admin_uploaded).length
                                        : documents.filter(f => !f.is_admin_uploaded).length;
                                const label = filter === 'all' ? 'All' : filter === 'admin' ? 'Admin' : 'User';

                                return (
                                    <button
                                        key={filter}
                                        onClick={() => setDocFilter(filter)}
                                        className={`relative px-4 py-2 text-xs transition-colors ${isActive
                                            ? 'text-sky-400'
                                            : 'text-slate-500 hover:text-slate-300'
                                            }`}
                                    >
                                        <span className="flex items-center gap-1.5">
                                            {label}
                                            <span className={`text-[10px] ${isActive ? 'text-sky-400/70' : 'text-slate-600'}`}>
                                                {count}
                                            </span>
                                        </span>
                                        {isActive && (
                                            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-sky-500 rounded-full" />
                                        )}
                                    </button>
                                );
                            })}
                        </div>
                    )}

                    {/* Document List */}
                    {loading ? (
                        <div className="flex justify-center p-4"><SpinnerIcon className="w-8 h-8 text-sky-500 animate-spin" /></div>
                    ) : (
                        <div className="space-y-2 mb-6 max-h-[250px] overflow-y-auto">
                            {documents.filter(doc => {
                                if (docFilter === 'all') return true;
                                if (docFilter === 'admin') return doc.is_admin_uploaded;
                                return !doc.is_admin_uploaded;
                            }).length === 0 && (
                                    <p className="text-center text-slate-500 py-4">
                                        {documents.length === 0 ? 'No documents found.' : `No ${docFilter === 'admin' ? 'admin' : 'user'} documents.`}
                                    </p>
                                )}
                            {documents.filter(doc => {
                                if (docFilter === 'all') return true;
                                if (docFilter === 'admin') return doc.is_admin_uploaded;
                                return !doc.is_admin_uploaded;
                            }).map((doc, idx) => (
                                <div key={idx} className="flex items-center justify-between p-3 bg-slate-800 rounded-lg border border-slate-700">
                                    <div className="flex items-center gap-3 overflow-hidden">
                                        <DocumentIcon className="w-5 h-5 text-sky-400 flex-shrink-0" />
                                        <div className="flex flex-col overflow-hidden">
                                            <span className="text-sm text-white truncate" title={doc.file.name}>{doc.file.name}</span>
                                            <div className="flex items-center gap-2">
                                                <span className="text-xs text-slate-500 uppercase">{doc.kind}</span>
                                                {doc.is_admin_uploaded && <span className="text-[10px] bg-sky-900/50 text-sky-200 px-1 rounded border border-sky-700/50">Admin Upload</span>}
                                                {doc.status === 'error' && <span className="text-[10px] bg-red-900/50 text-red-200 px-1 rounded border border-red-700/50">Failed</span>}
                                            </div>
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => handleDelete(doc.file.name, doc.kind)}
                                        className="p-2 text-slate-400 hover:text-red-400 hover:bg-red-900/20 rounded-full transition-colors"
                                        title="Delete"
                                    >
                                        <TrashIcon className="w-4 h-4" />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* File Size Limits Section */}
                    <div className="mt-6 pt-4 border-t border-slate-700">
                        <button
                            onClick={() => setLimitsExpanded(!limitsExpanded)}
                            className="flex items-center justify-between w-full text-left"
                        >
                            <span className="text-sm font-semibold text-slate-300">File Size Limits</span>
                            <span className={`text-slate-400 transform transition-transform ${limitsExpanded ? 'rotate-180' : ''}`}>▼</span>
                        </button>

                        {limitsExpanded && (
                            <div className="mt-4 space-y-3">
                                {limitsLoading ? (
                                    <div className="flex justify-center py-4">
                                        <SpinnerIcon className="w-5 h-5 text-sky-500 animate-spin" />
                                    </div>
                                ) : (
                                    <>
                                        <p className="text-xs text-slate-500 mb-3">Set total storage quota (in MB) for each document type.</p>
                                        <div className="grid grid-cols-3 gap-3">
                                            {(['pdf', 'docx', 'pptx', 'images', 'text', 'csv'] as const).map((type) => (
                                                <div key={type} className="flex items-center gap-2">
                                                    <label className="text-xs text-slate-400 uppercase w-14">{type}</label>
                                                    <div className="flex-1 flex flex-col">
                                                        <label className="block text-xs font-medium text-slate-400 mb-1">
                                                            {type.toUpperCase()} Quota (MB)
                                                        </label>
                                                        <input
                                                            type="number"
                                                            min="0"
                                                            step="0.1"
                                                            max="500"
                                                            value={formatSizeForDisplay(fileSizeLimits[type])}
                                                            onChange={(e) => setFileSizeLimits(prev => ({
                                                                ...prev,
                                                                [type]: parseSizeFromInput(e.target.value)
                                                            }))}
                                                            className="w-full px-3 py-1.5 text-sm bg-slate-800 border border-slate-600 rounded-lg focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500/50 text-white text-center appearance-none [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                                                            style={{ MozAppearance: 'textfield' }}
                                                        />
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                        <button
                                            onClick={handleSaveLimits}
                                            disabled={savingLimits}
                                            className="mt-3 w-full px-4 py-2 text-sm font-medium text-white bg-sky-600 hover:bg-sky-700 disabled:bg-slate-600 disabled:cursor-not-allowed rounded-lg transition-colors flex items-center justify-center gap-2"
                                        >
                                            {savingLimits && <SpinnerIcon className="w-4 h-4 animate-spin" />}
                                            {savingLimits ? 'Saving...' : 'Save Limits'}
                                        </button>
                                    </>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export const DashboardPage: React.FC<DashboardPageProps> = ({ users, onLogout, onNavigateToAddUser, onNavigateToConfig, onDeleteUser, onEditUser, onShowConfirmation }) => {
    const [searchQuery, setSearchQuery] = useState('');
    const [roleFilter, setRoleFilter] = useState<'all' | 'admin' | 'user'>('all');
    const [managingDocsUser, setManagingDocsUser] = useState<AdminUser | null>(null);

    const stats = useMemo(() => ({
        totalUsers: users.length,
        totalSessions: users.reduce((acc, user) => acc + user.sessions, 0),
        totalDocuments: users.reduce((acc, user) => acc + user.documents, 0),
        totalWebTools: users.reduce((acc, user) => acc + (user.mcpWebTools ?? 0), 0),
        totalLocalTools: users.reduce((acc, user) => acc + (user.mcpLocalTools ?? 0), 0),
    }), [users]);

    const filteredUsers = useMemo(() =>
        users.filter(user => {
            const matchesSearch = user.name.toLowerCase().includes(searchQuery.toLowerCase());
            const matchesRole = roleFilter === 'all' || user.role === roleFilter;
            return matchesSearch && matchesRole;
        }),
        [users, searchQuery, roleFilter]);

    const RoleBadge: React.FC<{ role: 'admin' | 'user' }> = ({ role }) => (
        <span className={`px-2.5 py-1 text-xs font-semibold rounded-full capitalize ${role === 'admin'
            ? 'bg-sky-500/20 text-sky-300'
            : 'bg-slate-700/50 text-slate-300'
            }`}>
            {role}
        </span>
    );

    return (
        <div className="flex h-screen w-full font-sans text-white">
            <div className="flex-1 flex flex-col overflow-hidden">
                {/* Header */}
                <header className="flex-shrink-0 flex items-center justify-between p-4 bg-slate-900/30 backdrop-blur-md">
                    <h1 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-teal-300 to-sky-400">
                        Admin Dashboard
                    </h1>
                    <div className="flex items-center gap-3">
                        <button
                            onClick={onNavigateToConfig}
                            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-300 bg-slate-800/40 border border-slate-600/50 hover:bg-sky-500/20 hover:text-sky-300 rounded-lg transition-colors"
                            title="Configuration"
                        >
                            <SettingsIcon className="w-5 h-5" />
                            Configuration
                        </button>
                        <button
                            onClick={onLogout}
                            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-300 bg-slate-800/40 border border-slate-600/50 hover:bg-red-500/20 hover:text-red-300 rounded-lg transition-colors"
                        >
                            <LogoutIcon className="w-5 h-5" />
                            Logout
                        </button>
                    </div>
                </header>

                {/* Main Content */}
                <main className="flex-1 overflow-y-auto p-6 lg:p-8 space-y-8">
                    {/* Stats Section */}
                    <section>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            <StatCard title="Total Users" value={stats.totalUsers} icon={<UserOutlineIcon className="w-8 h-8 text-sky-400" />} />
                            <StatCard title="Total Sessions" value={stats.totalSessions} icon={<ChatIcon className="w-8 h-8 text-teal-400" />} />
                            <StatCard title="Total Documents" value={stats.totalDocuments} icon={<FolderOpenIcon className="w-8 h-8 text-indigo-400" />} />
                            <StatCard title="Total Web Tools" value={stats.totalWebTools} icon={<SettingsIcon className="w-8 h-8 text-purple-400" />} />
                            <StatCard title="Total Local Tools" value={stats.totalLocalTools} icon={<SettingsIcon className="w-8 h-8 text-pink-400" />} />
                        </div>
                    </section>

                    {/* User Management Section */}
                    <section className="bg-slate-900/30 backdrop-blur-md border border-slate-500/30 rounded-xl p-6">
                        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
                            <h2 className="text-2xl font-bold text-white">User Management</h2>
                            <div className="flex items-center gap-4">
                                <div className="w-40">
                                    <CustomDropdown
                                        options={['all', 'admin', 'user']}
                                        value={roleFilter}
                                        onChange={(value) => setRoleFilter(value as 'all' | 'admin' | 'user')}
                                        placeholder="Filter by Role"
                                    />
                                </div>
                                <div className="relative">
                                    <input
                                        type="text"
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                        placeholder="Search users..."
                                        className="w-full md:w-64 pl-10 pr-4 py-2 text-sm rounded-lg transition-colors bg-slate-800/50 text-slate-200 border border-slate-600 focus:outline-none focus:border-sky-500"
                                        aria-label="Search users"
                                    />
                                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                        <SearchIcon className="w-5 h-5 text-slate-400" />
                                    </div>
                                </div>
                                <button onClick={onNavigateToAddUser} className="flex-shrink-0 flex items-center gap-2 px-4 py-2 font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded-lg transition-colors">
                                    <PlusIcon className="w-5 h-5" />
                                    Add User
                                </button>
                            </div>
                        </div>

                        {/* Users Table */}
                        <div className="overflow-x-auto">
                            <table className="w-full text-left">
                                <thead className="border-b border-slate-500/30 text-sm text-slate-400">
                                    <tr>
                                        <th className="p-4">Username</th>
                                        <th className="p-4">Role</th>
                                        <th className="p-4">Sessions</th>
                                        <th className="p-4">Documents</th>
                                        <th className="p-4">Web Tools</th>
                                        <th className="p-4">Local Tools</th>
                                        <th className="p-4">Joined On</th>
                                        <th className="p-4 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {filteredUsers.map(user => (
                                        <tr key={user.id} className="border-b border-slate-500/30 hover:bg-white/10 transition-colors">
                                            <td className="p-4 font-medium text-white">{user.name}</td>
                                            <td className="p-4"><RoleBadge role={user.role} /></td>
                                            <td className="p-4">{user.sessions}</td>
                                            <td className="p-4">{user.documents}</td>
                                            <td className="p-4">{user.mcpWebTools ?? 0}</td>
                                            <td className="p-4">{user.mcpLocalTools ?? 0}</td>
                                            <td className="p-4 text-sm text-slate-400">{new Date(user.createdAt).toLocaleDateString()}</td>
                                            <td className="p-4 text-right">
                                                <button
                                                    onClick={() => setManagingDocsUser(user)}
                                                    className="p-2 mr-2 text-slate-400 hover:text-indigo-400 hover:bg-indigo-900/50 rounded-full transition-colors"
                                                    title="Manage Documents"
                                                >
                                                    <FolderOpenIcon className="w-5 h-5" />
                                                </button>
                                                <button
                                                    onClick={() => onEditUser(user)}
                                                    className="p-2 mr-2 text-slate-400 hover:text-sky-400 hover:bg-sky-900/50 rounded-full transition-colors"
                                                    title="Edit User"
                                                >
                                                    <EditIcon className="w-5 h-5" />
                                                </button>
                                                <button
                                                    onClick={() => onDeleteUser(user.id)}
                                                    className="p-2 text-slate-400 hover:text-red-400 hover:bg-red-900/50 rounded-full transition-colors"
                                                    title="Delete User"
                                                >
                                                    <TrashIcon className="w-5 h-5" />
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                        {filteredUsers.length === 0 && (
                            <div className="text-center text-slate-500 p-8 border-2 border-dashed border-slate-600/50 rounded-lg mt-6">
                                <p>{users.length > 0 ? "No users match your search." : "No users found. Add a new user to get started."}</p>
                            </div>
                        )}
                    </section>
                </main>
            </div>
            {managingDocsUser && (
                <DocumentManagementModal
                    user={managingDocsUser}
                    onClose={() => setManagingDocsUser(null)}
                    onShowConfirmation={onShowConfirmation}
                />
            )}
        </div>
    );
};