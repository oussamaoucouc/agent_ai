import { API_BASE_URL } from '../constants';
import { 
    QueryRequest, 
    QueryTTSResponse, 
    FullAgentRequest, 
    FullAgentResponse, 
    QueryResponse, 
    UploadDocumentRequest,
    UploadDocumentResponse,
    ListDocumentsResponse,
    DeleteDocumentRequest,
    DeleteDocumentResponse,
    SetModelRequest,
    SetVoiceRequest,
    CancelRequest,
    Session,
    CreateSessionRequest,
    RenameSessionRequest,
    DeleteSessionRequest,
    SaveMessagesRequest,
    AdminUser,
    ConfigResponse,
    ConfigUpdateRequest,
    ModelsCatalogResponse,
    ConfigPathResponse,
    SessionSettingsResponse
} from '../types';

const handleResponse = async <T,>(response: Response): Promise<T> => {
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error occurred' }));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }
    // For POST requests that might not return a body but indicate success
    const contentType = response.headers.get("content-type");
    if (contentType && contentType.indexOf("application/json") !== -1) {
        return response.json() as Promise<T>;
    }
    // Create a generic success response if no JSON body is present
    return Promise.resolve({ success: true } as unknown as T);
};

export const query = async (request: QueryRequest, signal?: AbortSignal): Promise<QueryResponse> => {
    const response = await fetch(`${API_BASE_URL}/query_direct`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
        signal,
    });
    return handleResponse<QueryResponse>(response);
};

export const queryMcp = async (request: QueryRequest, signal?: AbortSignal): Promise<QueryResponse> => {
    const response = await fetch(`${API_BASE_URL}/query_mcp_direct`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
        signal,
    });
    return handleResponse<QueryResponse>(response);
};

export const queryAgent = async (request: QueryRequest, signal?: AbortSignal): Promise<QueryResponse> => {
    const response = await fetch(`${API_BASE_URL}/query_assistant_direct`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
        signal,
    });
    return handleResponse<QueryResponse>(response);
};

export const queryTTS = async (request: QueryRequest, signal?: AbortSignal): Promise<QueryTTSResponse> => {
    const response = await fetch(`${API_BASE_URL}/query_tts_direct`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
        signal,
    });
    return handleResponse<QueryTTSResponse>(response);
};

export const queryMcpTTS = async (request: QueryRequest, signal?: AbortSignal): Promise<QueryTTSResponse> => {
    const response = await fetch(`${API_BASE_URL}/query_mcp_tts_direct`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
        signal,
    });
    return handleResponse<QueryTTSResponse>(response);
};

export const queryAgentTTS = async (request: QueryRequest, signal?: AbortSignal): Promise<QueryTTSResponse> => {
    const response = await fetch(`${API_BASE_URL}/query_assistant_tts_direct`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
        signal,
    });
    return handleResponse<QueryTTSResponse>(response);
};


export const fullAgent = async (request: FullAgentRequest, signal?: AbortSignal): Promise<FullAgentResponse> => {
    const formData = new FormData();
    formData.append('file', request.file, 'recording.wav');
    formData.append('user_id', request.user_id);
    formData.append('session_id', request.session_id);
    if (request.system_prompt) {
        formData.append('system_prompt', request.system_prompt);
    }

    const response = await fetch(`${API_BASE_URL}/stt_query_tts_direct`, {
        method: 'POST',
        body: formData,
        signal,
    });
    return handleResponse<FullAgentResponse>(response);
};

export const fullAgentMcp = async (request: FullAgentRequest, signal?: AbortSignal): Promise<FullAgentResponse> => {
    const formData = new FormData();
    formData.append('file', request.file, 'recording.wav');
    formData.append('user_id', request.user_id);
    formData.append('session_id', request.session_id);
    if (request.system_prompt) {
        formData.append('system_prompt', request.system_prompt);
    }

    const response = await fetch(`${API_BASE_URL}/stt_query_mcp_tts_direct`, {
        method: 'POST',
        body: formData,
        signal,
    });
    return handleResponse<FullAgentResponse>(response);
};

export const fullAgentAgent = async (request: FullAgentRequest, signal?: AbortSignal): Promise<FullAgentResponse> => {
    const formData = new FormData();
    formData.append('file', request.file, 'recording.wav');
    formData.append('user_id', request.user_id);
    formData.append('session_id', request.session_id);
    if (request.system_prompt) {
        formData.append('system_prompt', request.system_prompt);
    }

    const response = await fetch(`${API_BASE_URL}/stt_query_assistant_tts_direct`, {
        method: 'POST',
        body: formData,
        signal,
    });
    return handleResponse<FullAgentResponse>(response);
};

export const uploadDocument = async (request: UploadDocumentRequest, signal?: AbortSignal): Promise<UploadDocumentResponse> => {
    const formData = new FormData();
    formData.append('file', request.file);
    formData.append('user_id', request.user_id);
    formData.append('session_id', request.session_id);

    // Assuming a new endpoint for document uploads exists on the backend
    const response = await fetch(`${API_BASE_URL}/upload_document`, {
        method: 'POST',
        body: formData,
        signal,
    });
    return handleResponse<UploadDocumentResponse>(response);
};

export const listDocuments = async (user_id: string, signal?: AbortSignal): Promise<ListDocumentsResponse> => {
    const url = new URL(`${API_BASE_URL}/list_documents`);
    url.searchParams.set('user_id', user_id);
    url.searchParams.set('ts', Date.now().toString());
    const response = await fetch(url, { method: 'GET', signal, cache: 'no-store' });
    return handleResponse<ListDocumentsResponse>(response);
};

export const deleteDocument = async (request: DeleteDocumentRequest, signal?: AbortSignal): Promise<DeleteDocumentResponse> => {
    const url = new URL(`${API_BASE_URL}/delete_document`);
    url.searchParams.set('user_id', request.user_id);
    url.searchParams.set('filename', request.filename);
    const response = await fetch(url.toString(), { method: 'DELETE', signal });
    return handleResponse<DeleteDocumentResponse>(response);
};

export const setModel = async (request: SetModelRequest, signal?: AbortSignal): Promise<{success: boolean}> => {
    const response = await fetch(`${API_BASE_URL}/set_model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal,
    });
    return handleResponse<{success: boolean}>(response);
};

export const setVoice = async (request: SetVoiceRequest, signal?: AbortSignal): Promise<{success: boolean}> => {
    const response = await fetch(`${API_BASE_URL}/set_voice`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal,
    });
    return handleResponse<{success: boolean}>(response);
};

// --- Session persistence API ---
export const getSessions = async (user_id: string, signal?: AbortSignal): Promise<Session[]> => {
    const url = new URL(`${API_BASE_URL}/sessions`);
    url.searchParams.set('user_id', user_id);
    url.searchParams.set('ts', Date.now().toString());
    const response = await fetch(url, { method: 'GET', signal, cache: 'no-store' });
    return handleResponse<Session[]>(response);
};

export const createSession = async (request: CreateSessionRequest, signal?: AbortSignal): Promise<Session> => {
    const response = await fetch(`${API_BASE_URL}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal,
    });
    return handleResponse<Session>(response);
};

export const renameSession = async (sessionId: string, request: RenameSessionRequest, signal?: AbortSignal): Promise<Session> => {
    const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/rename`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal,
    });
    return handleResponse<Session>(response);
};

export const deleteSession = async (sessionId: string, request: DeleteSessionRequest, signal?: AbortSignal): Promise<{status: string}> => {
    const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal,
    });
    return handleResponse<{status: string}>(response);
};

export const saveSessionMessages = async (sessionId: string, request: SaveMessagesRequest, signal?: AbortSignal): Promise<Session> => {
    const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/messages`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal,
    });
    return handleResponse<Session>(response);
};

export const cancelSession = async (request: CancelRequest): Promise<{status: string}> => {
    const response = await fetch(`${API_BASE_URL}/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
    });
    return handleResponse<{status: string}>(response);
};

// --- User management API ---
export const listUserStats = async (signal?: AbortSignal): Promise<Array<{ id: string; username: string; role: string; sessions: number; documents: number; createdAt: string }>> => {
    const url = new URL(`${API_BASE_URL}/users/stats`);
    // Add cache-busting param to avoid stale data across browsers
    url.searchParams.set('ts', Date.now().toString());
    const response = await fetch(url, { method: 'GET', signal, cache: 'no-store' });
    return handleResponse<Array<{ id: string; username: string; role: string; sessions: number; documents: number; createdAt: string }>>(response);
};

export const createUser = async (username: string, password: string, role: 'admin' | 'user', signal?: AbortSignal): Promise<AdminUser> => {
    const response = await fetch(`${API_BASE_URL}/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, role }),
        signal,
    });
    const u = await handleResponse<{ id: string; username: string; role: string; createdAt: string }>(response);
    // New users have zero sessions/documents initially
    return { id: u.id, name: u.username, role: u.role as 'admin' | 'user', sessions: 0, documents: 0, createdAt: u.createdAt };
};

export const updateUser = async (user_id: string, payload: { password?: string; role?: 'admin' | 'user' }, signal?: AbortSignal): Promise<AdminUser> => {
    const response = await fetch(`${API_BASE_URL}/users/${user_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal,
    });
    const u = await handleResponse<{ id: string; username: string; role: string; createdAt: string }>(response);
    // Caller should refresh stats afterward to get counts
    return { id: u.id, name: u.username, role: u.role as 'admin' | 'user', sessions: 0, documents: 0, createdAt: u.createdAt };
};

export const deleteUser = async (user_id: string, signal?: AbortSignal): Promise<{status: string}> => {
    const response = await fetch(`${API_BASE_URL}/users/${user_id}`, { method: 'DELETE', signal });
    return handleResponse<{status: string}>(response);
};

export const loginUser = async (username: string, password: string, signal?: AbortSignal): Promise<{ user_id: string; session_id: string; username: string; role: string }> => {
    const response = await fetch(`${API_BASE_URL}/users/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
        signal,
    });
    return handleResponse<{ user_id: string; session_id: string; username: string; role: string }>(response);
};

// --- Admin Configuration API ---
export const getConfig = async (user_id: string, signal?: AbortSignal): Promise<ConfigResponse> => {
    const url = new URL(`${API_BASE_URL}/config`);
    url.searchParams.set('user_id', user_id);
    url.searchParams.set('ts', Date.now().toString());
    const response = await fetch(url, { method: 'GET', signal, cache: 'no-store' });
    return handleResponse<ConfigResponse>(response);
};

export const updateConfig = async (payload: ConfigUpdateRequest, signal?: AbortSignal): Promise<ConfigResponse> => {
    const response = await fetch(`${API_BASE_URL}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal,
    });
    return handleResponse<ConfigResponse>(response);
};

export const getModelsCatalog = async (user_id: string, signal?: AbortSignal): Promise<ModelsCatalogResponse> => {
    const url = new URL(`${API_BASE_URL}/models`);
    url.searchParams.set('user_id', user_id);
    url.searchParams.set('ts', Date.now().toString());
    const response = await fetch(url, { method: 'GET', signal, cache: 'no-store' });
    // Backend returns { models: string[] }; normalize to { available_models: string[] }
    const raw = await response.json();
    if (!response.ok) {
        throw new Error(raw?.detail || `Failed to fetch models catalog: ${response.status}`);
    }
    const models = Array.isArray(raw?.models) ? raw.models : [];
    return { available_models: models };
};

export const getConfigPath = async (user_id: string, signal?: AbortSignal): Promise<ConfigPathResponse> => {
    const url = new URL(`${API_BASE_URL}/config_path`);
    url.searchParams.set('user_id', user_id);
    url.searchParams.set('ts', Date.now().toString());
    const response = await fetch(url, { method: 'GET', signal, cache: 'no-store' });
    return handleResponse<ConfigPathResponse>(response);
};

// --- Per-session settings ---
export const getSessionSettings = async (user_id: string, session_id: string, signal?: AbortSignal): Promise<SessionSettingsResponse> => {
    const url = new URL(`${API_BASE_URL}/sessions/${session_id}/settings`);
    url.searchParams.set('user_id', user_id);
    url.searchParams.set('ts', Date.now().toString());
    const response = await fetch(url, { method: 'GET', signal, cache: 'no-store' });
    return handleResponse<SessionSettingsResponse>(response);
};
