import React, { useState } from 'react';

interface AddUserPageProps {
    onAddUser: (newUser: { name: string; password: string; role: 'user' | 'admin' }) => void;
    onCancel: () => void;
}

export const AddUserPage: React.FC<AddUserPageProps> = ({ onAddUser, onCancel }) => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [role, setRole] = useState<'user' | 'admin'>('user');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (username.trim() && password.trim()) {
            onAddUser({ name: username.trim(), password: password.trim(), role });
        } else {
            alert('Username and password cannot be empty.');
        }
    };

    return (
        <div className="flex items-center justify-center h-screen bg-gradient-to-br from-gray-900 to-gray-800">
            <div className="w-full max-w-lg p-8 space-y-8 bg-gray-800/50 border border-gray-700 rounded-2xl shadow-2xl">
                <div className="text-left">
                    <h1 className="text-2xl font-bold text-white">
                        Create New User
                    </h1>
                    <p className="mt-2 text-gray-400">Fill in the details below to add a new user to the system.</p>
                </div>
                <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
                    <div className="rounded-md shadow-sm space-y-4">
                        <div>
                            <label htmlFor="username" className="block text-sm font-medium text-gray-300 mb-2">Username</label>
                            <input
                                id="username"
                                name="username"
                                type="text"
                                required
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className="appearance-none rounded-lg relative block w-full px-3 py-3 border border-gray-600 bg-gray-900 placeholder-gray-500 text-white focus:outline-none focus:ring-sky-500 focus:border-sky-500 focus:z-10 sm:text-sm"
                                placeholder="e.g., John Doe"
                            />
                        </div>
                        <div>
                            <label htmlFor="password-create" className="block text-sm font-medium text-gray-300 mb-2">Password</label>
                            <input
                                id="password-create"
                                name="password"
                                type="password"
                                required
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="appearance-none rounded-lg relative block w-full px-3 py-3 border border-gray-600 bg-gray-900 placeholder-gray-500 text-white focus:outline-none focus:ring-sky-500 focus:border-sky-500 focus:z-10 sm:text-sm"
                                placeholder="Enter a strong password"
                            />
                        </div>
                        <div>
                            <label htmlFor="role" className="block text-sm font-medium text-gray-300 mb-2">Role</label>
                             <select
                                id="role"
                                name="role"
                                value={role}
                                onChange={(e) => setRole(e.target.value as 'user' | 'admin')}
                                className="w-full appearance-none px-3 py-3 text-sm rounded-lg transition-colors bg-gray-900 text-white border border-gray-600 focus:outline-none focus:border-sky-500"
                            >
                                <option value="user">User</option>
                                <option value="admin">Admin</option>
                            </select>
                        </div>
                    </div>

                    <div className="flex items-center justify-end gap-4 pt-2">
                         <button
                            type="button"
                            onClick={onCancel}
                            className="group relative flex justify-center py-3 px-6 border border-gray-600 text-sm font-medium rounded-lg text-gray-300 bg-transparent hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 focus:ring-offset-gray-900 transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            className="group relative flex justify-center py-3 px-6 border border-transparent text-sm font-medium rounded-lg text-white bg-sky-600 hover:bg-sky-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-sky-500 focus:ring-offset-gray-900 transition-colors"
                        >
                            Save User
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};