import React, { useState } from 'react';

interface EditUserPageProps {
    userId: string;
    username: string;
    currentRole: 'user' | 'admin';
    onSave: (payload: { password: string; role?: 'user' | 'admin' }) => void;
    onCancel: () => void;
}

export const EditUserPage: React.FC<EditUserPageProps> = ({ username, currentRole, onSave, onCancel }) => {
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [role, setRole] = useState<'user' | 'admin'>(currentRole);
    const [showPassword, setShowPassword] = useState(false);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        const newPass = password.trim();
        const confirmPass = confirmPassword.trim();
        if (!newPass) {
            alert('Password cannot be empty.');
            return;
        }
        if (newPass !== confirmPass) {
            alert('Passwords do not match.');
            return;
        }
        onSave({ password: newPass, role });
    };

    return (
        <div className="flex items-center justify-center h-screen">
            <div className="w-full max-w-lg p-8 space-y-8 bg-slate-900/30 backdrop-blur-2xl border border-slate-500/30 rounded-2xl shadow-2xl">
                <div className="text-left">
                    <h1 className="text-2xl font-bold text-white">Edit User</h1>
                    <p className="mt-2 text-slate-400">Reset password and optionally change role for the selected user.</p>
                </div>

                <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
                    <div className="rounded-md shadow-sm space-y-4">
                        <div>
                            <label htmlFor="username" className="block text-sm font-medium text-slate-300 mb-2">Username</label>
                            <input
                                id="username"
                                name="username"
                                type="text"
                                value={username}
                                disabled
                                className="appearance-none rounded-lg relative block w-full px-3 py-3 border border-slate-600 bg-slate-800/50 text-slate-400 focus:outline-none sm:text-sm"
                            />
                        </div>
                        <div>
                            <label htmlFor="password-edit" className="block text-sm font-medium text-slate-300 mb-2">New Password</label>
                            <div className="relative">
                                <input
                                    id="password-edit"
                                    name="password"
                                    type={showPassword ? 'text' : 'password'}
                                    required
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="appearance-none rounded-lg relative block w-full px-3 py-3 border border-slate-600 bg-slate-800/50 placeholder-slate-500 text-white focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 focus:z-10 sm:text-sm"
                                    placeholder="Enter a new password"
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPassword(v => !v)}
                                    className="absolute right-2 top-1/2 -translate-y-1/2 text-sm text-slate-400 hover:text-slate-200"
                                >
                                    {showPassword ? 'Hide' : 'Show'}
                                </button>
                            </div>
                        </div>
                        <div>
                            <label htmlFor="confirm-password-edit" className="block text-sm font-medium text-slate-300 mb-2">Confirm Password</label>
                            <input
                                id="confirm-password-edit"
                                name="confirmPassword"
                                type={showPassword ? 'text' : 'password'}
                                required
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                className="appearance-none rounded-lg relative block w-full px-3 py-3 border border-slate-600 bg-slate-800/50 placeholder-slate-500 text-white focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 focus:z-10 sm:text-sm"
                                placeholder="Re-enter the new password"
                            />
                        </div>
                        <div>
                            <label htmlFor="role-edit" className="block text-sm font-medium text-slate-300 mb-2">Role</label>
                            <select
                                id="role-edit"
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
                            className="group relative flex justify-center py-3 px-6 border border-transparent text-sm font-medium rounded-lg text-white bg-sky-600 hover:bg-sky-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-sky-500 focus:ring-offset-slate-900 transition-colors"
                        >
                            Save Changes
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};