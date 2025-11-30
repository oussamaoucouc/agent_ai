import React, { useState, useMemo } from 'react';
import { AdminUser } from '../types';
import { LogoutIcon, UserOutlineIcon, ChatIcon, FolderOpenIcon, PlusIcon, TrashIcon, SearchIcon, EditIcon, SettingsIcon } from './icons';
import { CustomDropdown } from './CustomDropdown';

interface DashboardPageProps {
    users: AdminUser[];
    onLogout: () => void;
    onNavigateToAddUser: () => void;
    onNavigateToConfig: () => void;
    onDeleteUser: (userId: string) => void;
    onEditUser: (user: AdminUser) => void;
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

export const DashboardPage: React.FC<DashboardPageProps> = ({ users, onLogout, onNavigateToAddUser, onNavigateToConfig, onDeleteUser, onEditUser }) => {
    const [searchQuery, setSearchQuery] = useState('');
    const [roleFilter, setRoleFilter] = useState<'all' | 'admin' | 'user'>('all');

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
        </div>
    );
};