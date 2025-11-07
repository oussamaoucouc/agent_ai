import React, { useState } from 'react';
import { AdminUser } from '../types';
import { LogoutIcon, UsersIcon, ChatIcon, FolderOpenIcon, PlusIcon, TrashIcon } from './icons';

// Mock Data for demonstration purposes
const initialUsers: AdminUser[] = [
    { id: '1', name: 'Alice', sessions: 5, documents: 2, createdAt: '2023-10-26T10:00:00Z' },
    { id: '2', name: 'Bob', sessions: 12, documents: 10, createdAt: '2023-10-25T14:30:00Z' },
    { id: '3', name: 'Charlie', sessions: 2, documents: 0, createdAt: '2023-10-27T08:45:00Z' },
    { id: '4', name: 'Diana', sessions: 8, documents: 4, createdAt: '2023-10-27T11:20:00Z' },
];

const StatCard: React.FC<{ title: string; value: string | number; icon: React.ReactNode }> = ({ title, value, icon }) => (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 flex items-center gap-6 transform hover:-translate-y-1 transition-transform duration-300">
        <div className="bg-slate-700 p-4 rounded-full">{icon}</div>
        <div>
            <p className="text-gray-400 text-sm font-medium">{title}</p>
            <p className="text-3xl font-bold text-white">{value}</p>
        </div>
    </div>
);

export const DashboardPage: React.FC<{ onLogout: () => void }> = ({ onLogout }) => {
    const [users, setUsers] = useState<AdminUser[]>(initialUsers);
    const [newUserName, setNewUserName] = useState('');

    const stats = {
        totalUsers: users.length,
        totalSessions: users.reduce((acc, user) => acc + user.sessions, 0),
        totalDocuments: users.reduce((acc, user) => acc + user.documents, 0),
    };

    const handleAddUser = (e: React.FormEvent) => {
        e.preventDefault();
        if (newUserName.trim() && !users.some(u => u.name.toLowerCase() === newUserName.trim().toLowerCase())) {
            const newUser: AdminUser = {
                id: crypto.randomUUID(),
                name: newUserName.trim(),
                sessions: 0,
                documents: 0,
                createdAt: new Date().toISOString(),
            };
            setUsers([newUser, ...users]);
            setNewUserName('');
        } else {
            alert('Username is empty or already exists.');
        }
    };

    const handleDeleteUser = (userId: string) => {
        if (window.confirm('Are you sure you want to delete this user and all their data?')) {
            setUsers(users.filter(user => user.id !== userId));
        }
    };

    return (
        <div className="flex h-screen w-full font-sans bg-gradient-to-br from-gray-900 to-gray-800 text-white">
            <div className="flex-1 flex flex-col overflow-hidden">
                {/* Header */}
                <header className="flex-shrink-0 flex items-center justify-between p-4 bg-gray-900/50 border-b border-gray-700">
                    <h1 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-teal-300 to-sky-500">
                        Admin Dashboard
                    </h1>
                    <button
                        onClick={onLogout}
                        className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-300 bg-slate-800 hover:bg-red-800/50 hover:text-red-300 rounded-lg transition-colors"
                    >
                        <LogoutIcon className="w-5 h-5" />
                        Logout
                    </button>
                </header>

                {/* Main Content */}
                <main className="flex-1 overflow-y-auto p-6 lg:p-8 space-y-8">
                    {/* Stats Section */}
                    <section>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            <StatCard title="Total Users" value={stats.totalUsers} icon={<UsersIcon className="w-8 h-8 text-sky-400" />} />
                            <StatCard title="Total Sessions" value={stats.totalSessions} icon={<ChatIcon className="w-8 h-8 text-teal-400" />} />
                            <StatCard title="Total Documents" value={stats.totalDocuments} icon={<FolderOpenIcon className="w-8 h-8 text-indigo-400" />} />
                        </div>
                    </section>
                    
                    {/* User Management Section */}
                    <section className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
                        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
                            <h2 className="text-2xl font-bold text-white">User Management</h2>
                            <form onSubmit={handleAddUser} className="flex items-center gap-2">
                                <input
                                    type="text"
                                    value={newUserName}
                                    onChange={(e) => setNewUserName(e.target.value)}
                                    placeholder="Enter new username"
                                    className="px-3 py-2 text-sm rounded-lg transition-colors bg-slate-800 text-gray-200 border-2 border-slate-700 focus:outline-none focus:border-sky-500"
                                    aria-label="New username"
                                />
                                <button type="submit" className="flex items-center gap-2 px-4 py-2 font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded-lg transition-colors disabled:bg-gray-600" disabled={!newUserName.trim()}>
                                    <PlusIcon className="w-5 h-5" />
                                    Add User
                                </button>
                            </form>
                        </div>
                        
                        {/* Users Table */}
                        <div className="overflow-x-auto">
                            <table className="w-full text-left">
                                <thead className="border-b border-slate-600 text-sm text-gray-400">
                                    <tr>
                                        <th className="p-4">Username</th>
                                        <th className="p-4">Sessions</th>
                                        <th className="p-4">Documents</th>
                                        <th className="p-4">Joined On</th>
                                        <th className="p-4 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {users.map(user => (
                                        <tr key={user.id} className="border-b border-slate-700 hover:bg-slate-800 transition-colors">
                                            <td className="p-4 font-medium text-white">{user.name}</td>
                                            <td className="p-4">{user.sessions}</td>
                                            <td className="p-4">{user.documents}</td>
                                            <td className="p-4 text-sm text-gray-400">{new Date(user.createdAt).toLocaleDateString()}</td>
                                            <td className="p-4 text-right">
                                                <button
                                                    onClick={() => handleDeleteUser(user.id)}
                                                    className="p-2 text-gray-400 hover:text-red-400 hover:bg-red-900/50 rounded-full transition-colors"
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
                         {users.length === 0 && (
                            <div className="text-center text-gray-500 p-8 border-2 border-dashed border-slate-700 rounded-lg mt-6">
                                <p>No users found. Add a new user to get started.</p>
                            </div>
                        )}
                    </section>
                </main>
            </div>
        </div>
    );
};
