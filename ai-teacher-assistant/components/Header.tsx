import React from 'react';
import { MenuIcon } from './icons';

interface HeaderProps {
    user: string;
    onToggleSidebar: () => void;
}

export const Header: React.FC<HeaderProps> = ({ user, onToggleSidebar }) => {
    return (
        <header className="flex-shrink-0 flex items-center justify-between p-4 bg-slate-900/30 backdrop-blur-md">
            <div className="flex items-center gap-4">
                 <button
                    onClick={onToggleSidebar}
                    className="p-1.5 text-slate-300 hover:text-white hover:bg-white/10 rounded-md transition-colors"
                    aria-label="Open sidebar"
                >
                    <MenuIcon className="w-6 h-6" />
                </button>
                <h1 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-teal-300 to-sky-400">
                    AI Assistant
                </h1>
            </div>
            <div className="flex items-center gap-4">
                <div className="text-slate-400 text-sm">
                    Welcome, <span className="font-semibold text-slate-200">{user}</span>
                </div>
            </div>
        </header>
    );
};