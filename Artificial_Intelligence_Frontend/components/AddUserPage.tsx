import React, { useState } from 'react';

interface AddUserPageProps {
    onAddUser: (newUser: { name: string; password: string; role: 'user' | 'admin' }) => void;
    onCancel: () => void;
}

export const AddUserPage: React.FC<AddUserPageProps> = ({ onAddUser, onCancel }) => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [role, setRole] = useState<'user' | 'admin'>('user');
    const [touched, setTouched] = useState(false);

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/i;
    const isValidEmail = emailRegex.test(username.trim());

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        setTouched(true);
        const email = username.trim();
        if (!emailRegex.test(email) || !password.trim()) {
            return; // require valid email + non-empty password
        }
        onAddUser({ name: email, password: password.trim(), role });
    };

    return (
        <div className="flex items-center justify-center h-screen">
            <div className="w-full max-w-lg p-8 space-y-8 bg-slate-900/30 backdrop-blur-2xl border border-slate-500/30 rounded-2xl shadow-2xl">
                <div className="text-left">
                    <h1 className="text-2xl font-bold text-white">
                        Create New User
                    </h1>
                    <p className="mt-2 text-slate-400">Fill in the details below to add a new user to the system.</p>
                </div>
                <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
                    <div className="rounded-md shadow-sm space-y-4">
                        <div>
                            <label htmlFor="username" className="block text-sm font-medium text-slate-300 mb-2">Email</label>
                            <input
                                id="username"
                                name="username"
                                type="email"
                                required
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                onBlur={() => setTouched(true)}
                                aria-invalid={touched && !isValidEmail}
                                aria-describedby="adduser-email-help"
                                className="appearance-none rounded-lg relative block w-full px-3 py-3 border border-slate-600 bg-slate-800/50 placeholder-slate-500 text-white focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 focus:z-10 sm:text-sm"
                                placeholder="Email (e.g., user@example.com)"
                            />
                            {touched && !isValidEmail && (
                                <p id="adduser-email-help" className="mt-2 text-xs text-red-400">Enter a valid email with a domain, like user@example.com.</p>
                            )}
                        </div>
                        <div>
                            <label htmlFor="password-create" className="block text-sm font-medium text-slate-300 mb-2">Password</label>
                            <input
                                id="password-create"
                                name="password"
                                type="password"
                                required
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="appearance-none rounded-lg relative block w-full px-3 py-3 border border-slate-600 bg-slate-800/50 placeholder-slate-500 text-white focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 focus:z-10 sm:text-sm"
                                placeholder="Enter a strong password"
                            />
                        </div>
                        <div>
                            <label htmlFor="role" className="block text-sm font-medium text-slate-300 mb-2">Role</label>
                             <select
                                id="role"
                                name="role"
                                value={role}
                                onChange={(e) => setRole(e.target.value as 'user' | 'admin')}
                                className="w-full appearance-none px-3 py-3 text-sm rounded-lg transition-colors bg-slate-800/50 text-white border border-slate-600 focus:outline-none focus:border-sky-500"
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
                            className="group relative flex justify-center py-3 px-6 border border-slate-600 text-sm font-medium rounded-lg text-slate-300 bg-slate-800/40 hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-slate-500 focus:ring-offset-slate-900 transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={touched && (!isValidEmail || !password.trim())}
                            className="group relative flex justify-center py-3 px-6 border border-transparent text-sm font-medium rounded-lg text-white bg-sky-600 hover:bg-sky-700 disabled:bg-slate-700 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-sky-500 focus:ring-offset-slate-900 transition-colors"
                        >
                            Save User
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};