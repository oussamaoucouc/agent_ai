import { Session, QueryMode } from '../types';

// Lightweight persistence for auth state: store current user/role/username in sessionStorage.
// Using sessionStorage avoids cross-tab/session mixing that can cause role leakage.
// Session messages and lists remain server-backed and ephemeral here.

let memorySessions: Record<string, Session[]> = {};
let memoryCurrentUser: string | null = null;
let memoryCurrentUsername: string | null = null;
let memoryCurrentUserRole: 'admin' | 'user' | null = null;
let memoryAuthToken: string | null = null;

// Keys used in sessionStorage
const LS_KEYS = {
  user: 'app.currentUser',
  username: 'app.currentUsername',
  role: 'app.currentUserRole',
  activeSession: 'app.activeSessionId',
  adminView: 'app.adminView',
  token: 'app.authToken',
  queryMode: 'app.queryMode',
  spokenResponses: 'app.spokenResponses',
  sidebarOpen: 'app.sidebarOpen',
};

const hasSessionStorage = (): boolean => {
  try {
    return typeof window !== 'undefined' && !!window.sessionStorage;
  } catch {
    return false;
  }
};

const lsGet = (key: string): string | null => {
  if (!hasSessionStorage()) return null;
  try {
    const val = window.sessionStorage.getItem(key);
    return val === null ? null : val;
  } catch {
    return null;
  }
};

const lsSet = (key: string, value: string): void => {
  if (!hasSessionStorage()) return;
  try {
    window.sessionStorage.setItem(key, value);
  } catch {
    // ignore write failures (e.g., quota)
  }
};

const lsRemove = (key: string): void => {
  if (!hasSessionStorage()) return;
  try {
    window.sessionStorage.removeItem(key);
  } catch {
    // ignore
  }
};

export const getSessionsForUser = (userId: string): Session[] => {
  return memorySessions[userId] || [];
};

export const saveSessionsForUser = (userId: string, sessions: Session[]) => {
  memorySessions[userId] = sessions;
};

export const getCurrentUser = (): string | null => {
  // Prefer memory value; otherwise try localStorage
  if (memoryCurrentUser) return memoryCurrentUser;
  const persisted = lsGet(LS_KEYS.user);
  memoryCurrentUser = persisted;
  return persisted;
};

export const setCurrentUser = (userId: string) => {
  memoryCurrentUser = userId;
  lsSet(LS_KEYS.user, userId);
};

export const clearCurrentUser = () => {
  memoryCurrentUser = null;
  memoryCurrentUsername = null;
  memoryCurrentUserRole = null;
  memoryAuthToken = null;
  lsRemove(LS_KEYS.user);
  lsRemove(LS_KEYS.username);
  lsRemove(LS_KEYS.role);
  lsRemove(LS_KEYS.activeSession);
  lsRemove(LS_KEYS.adminView);
  lsRemove(LS_KEYS.token);
};

export const getCurrentUserRole = (): 'admin' | 'user' | null => {
  if (memoryCurrentUserRole) return memoryCurrentUserRole;
  const persisted = lsGet(LS_KEYS.role) as 'admin' | 'user' | null;
  memoryCurrentUserRole = persisted;
  return persisted;
};

export const setCurrentUserRole = (role: 'admin' | 'user') => {
  memoryCurrentUserRole = role;
  lsSet(LS_KEYS.role, role);
};

export const getCurrentUsername = (): string | null => {
  if (memoryCurrentUsername) return memoryCurrentUsername;
  const persisted = lsGet(LS_KEYS.username);
  memoryCurrentUsername = persisted;
  return persisted;
};

export const setCurrentUsername = (username: string) => {
  memoryCurrentUsername = username;
  lsSet(LS_KEYS.username, username);
};

export const getAuthToken = (): string | null => {
  if (memoryAuthToken) return memoryAuthToken;
  const persisted = lsGet(LS_KEYS.token);
  memoryAuthToken = persisted;
  return persisted;
};

export const setAuthToken = (token: string) => {
  memoryAuthToken = token;
  lsSet(LS_KEYS.token, token);
};

export const getActiveSessionId = (): string | null => {
  const persisted = lsGet(LS_KEYS.activeSession);
  return persisted;
};

export const setActiveSessionId = (sessionId: string) => {
  lsSet(LS_KEYS.activeSession, sessionId);
};

export const getAdminView = (): string | null => {
  const persisted = lsGet(LS_KEYS.adminView);
  return persisted;
};

export const setAdminView = (view: 'dashboard' | 'addUser' | 'editUser' | 'config') => {
  lsSet(LS_KEYS.adminView, view);
};

export const getQueryMode = (): QueryMode | null => {
  const val = lsGet(LS_KEYS.queryMode);
  return val === 'agent' || val === 'direct' || val === 'tools' ? (val as QueryMode) : null;
};

export const setQueryMode = (mode: QueryMode) => {
  lsSet(LS_KEYS.queryMode, mode);
};

export const getSpokenResponses = (): boolean => {
    const persisted = lsGet(LS_KEYS.spokenResponses);
    // Default to true if the value is not found or is not 'false'
    return persisted !== 'false';
};

export const setSpokenResponses = (isEnabled: boolean) => {
    lsSet(LS_KEYS.spokenResponses, String(isEnabled));
};

export const getSidebarOpen = (): boolean => {
    const persisted = lsGet(LS_KEYS.sidebarOpen);
    // Default to true on desktop if not set, false on mobile
    if (persisted === null) {
        return window.innerWidth >= 1024;
    }
    return persisted === 'true';
};

export const setSidebarOpen = (isOpen: boolean) => {
    lsSet(LS_KEYS.sidebarOpen, String(isOpen));
};
