import { Session } from '../types';

const STORAGE_KEY = 'ai_assistant_app_data';
const CURRENT_USER_KEY = 'ai_assistant_current_user';

interface AppData {
    [userId: string]: Session[];
}

const getAllData = (): AppData => {
    try {
        const data = localStorage.getItem(STORAGE_KEY);
        return data ? JSON.parse(data) : {};
    } catch (error) {
        console.error("Failed to parse storage data:", error);
        return {};
    }
};

const saveAllData = (data: AppData) => {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (error) {
        console.error("Failed to save data to storage:", error);
    }
};

export const getSessionsForUser = (userId: string): Session[] => {
    const data = getAllData();
    return data[userId] || [];
};

export const saveSessionsForUser = (userId: string, sessions: Session[]) => {
    const data = getAllData();
    data[userId] = sessions;
    saveAllData(data);
};

export const getCurrentUser = (): string | null => {
    return localStorage.getItem(CURRENT_USER_KEY);
};

export const setCurrentUser = (userId: string) => {
    localStorage.setItem(CURRENT_USER_KEY, userId);
};

export const clearCurrentUser = () => {
    localStorage.removeItem(CURRENT_USER_KEY);
};