import { Session } from '../types';

// In-memory, non-persistent storage. All persistence is handled by the backend DB.
// This module now only keeps ephemeral UI state for the current runtime.

let memorySessions: Record<string, Session[]> = {};
let memoryCurrentUser: string | null = null;
let memoryCurrentUsername: string | null = null;
let memoryCurrentUserRole: 'admin' | 'user' | null = null;

export const getSessionsForUser = (userId: string): Session[] => {
    return memorySessions[userId] || [];
};

export const saveSessionsForUser = (userId: string, sessions: Session[]) => {
    memorySessions[userId] = sessions;
};

export const getCurrentUser = (): string | null => {
    return memoryCurrentUser;
};

export const setCurrentUser = (userId: string) => {
    memoryCurrentUser = userId;
};

export const clearCurrentUser = () => {
    memoryCurrentUser = null;
    memoryCurrentUsername = null;
    memoryCurrentUserRole = null;
};

export const getCurrentUserRole = (): 'admin' | 'user' | null => {
    return memoryCurrentUserRole;
};

export const setCurrentUserRole = (role: 'admin' | 'user') => {
    memoryCurrentUserRole = role;
};

export const getCurrentUsername = (): string | null => {
    return memoryCurrentUsername;
};

export const setCurrentUsername = (username: string) => {
    memoryCurrentUsername = username;
};