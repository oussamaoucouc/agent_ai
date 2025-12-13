import { API_BASE_URL } from '../constants';
import { VoicesCatalogResponse, McpToolsCatalogResponse, SetMcpToolsRequest, McpStdioToolsCatalogResponse, ModelsCatalogLabeledResponse, VoicesCatalogLabeledResponse } from '../types';
import { getAuthToken, setAuthToken } from './storageService';
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
    SessionSettingsResponse,
    VisemeData
} from '../types';

const authHeaders = (): Record<string, string> => {
    const token = getAuthToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
};

const authedFetch = async (url: string, init: RequestInit = {}): Promise<Response> => {
    const res = await fetch(url, init);
    if (res.status !== 401) return res;
    try {
        const refreshRes = await fetch(`${API_BASE_URL}/users/refresh`, { method: 'POST', credentials: 'include' });
        if (!refreshRes.ok) {
            // Refresh failed, preventing infinite loop or dead end.
            // Dispatch event so App.tsx can handle logout/UI.
            window.dispatchEvent(new CustomEvent("auth:session_expired"));
            return res;
        }
        const data = await refreshRes.json().catch(() => null) as any;
        const newToken = data?.access_token;
        if (!newToken) {
            window.dispatchEvent(new CustomEvent("auth:session_expired"));
            return res;
        }
        setAuthToken(newToken);
        const newInit: RequestInit = { ...init, headers: { ...(init.headers as any || {}), ...authHeaders() } };
        // Retry original request with new token
        const retryRes = await fetch(url, newInit);
        // If retry still fails with 401, then we really are out of luck
        if (retryRes.status === 401) {
            window.dispatchEvent(new CustomEvent("auth:session_expired"));
        }
        return retryRes;
    } catch {
        window.dispatchEvent(new CustomEvent("auth:session_expired"));
        return res;
    }
};

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

export const query = async (
    request: QueryRequest,
    signal?: AbortSignal,
    onChunk?: (text: string) => void
): Promise<QueryResponse> => {
    const response = await authedFetch(`${API_BASE_URL}/query_direct`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(request),
        signal,
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error occurred' }));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    // Check if it's a streaming response
    const contentType = response.headers.get('content-type');
    if (contentType?.includes('text/event-stream') && onChunk) {
        // Handle SSE streaming
        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let fullResponse = '';
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || ''; // Keep incomplete chunk in buffer

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.content) {
                            onChunk(data.content);
                            fullResponse += data.content;
                        }
                        if (data.done && data.full_response) {
                            fullResponse = data.full_response;
                        }
                        if (data.error) {
                            throw new Error(data.error);
                        }
                    } catch (e) {
                        // Ignore parse errors for incomplete chunks
                        if (e instanceof SyntaxError) continue;
                        throw e;
                    }
                }
            }
        }

        return {
            user_id: request.user_id,
            session_id: request.session_id,
            response: fullResponse
        };
    } else {
        // Fallback to non-streaming response
        return handleResponse<QueryResponse>(response);
    }
};

export const queryMcp = async (
    request: QueryRequest,
    signal?: AbortSignal,
    onChunk?: (text: string) => void
): Promise<QueryResponse> => {
    const response = await authedFetch(`${API_BASE_URL}/query_mcp_direct`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(request),
        signal,
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error occurred' }));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    // Check if it's a streaming response
    const contentType = response.headers.get('content-type');
    if (contentType?.includes('text/event-stream') && onChunk) {
        // Handle SSE streaming
        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let fullResponse = '';
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || ''; // Keep incomplete chunk in buffer

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.content) {
                            onChunk(data.content);
                            fullResponse += data.content;
                        }
                        if (data.done && data.full_response) {
                            fullResponse = data.full_response;
                        }
                        if (data.error) {
                            throw new Error(data.error);
                        }
                    } catch (e) {
                        // Ignore parse errors for incomplete chunks
                        if (e instanceof SyntaxError) continue;
                        throw e;
                    }
                }
            }
        }

        return {
            user_id: request.user_id,
            session_id: request.session_id,
            response: fullResponse
        };
    } else {
        // Fallback to non-streaming response
        return handleResponse<QueryResponse>(response);
    }
};

export const queryAgent = async (
    request: QueryRequest,
    signal?: AbortSignal,
    onChunk?: (text: string) => void
): Promise<QueryResponse> => {
    const response = await authedFetch(`${API_BASE_URL}/query_assistant_direct`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(request),
        signal,
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error occurred' }));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    // Check if it's a streaming response
    const contentType = response.headers.get('content-type');
    if (contentType?.includes('text/event-stream') && onChunk) {
        // Handle SSE streaming
        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let fullResponse = '';
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || ''; // Keep incomplete chunk in buffer

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.content) {
                            onChunk(data.content);
                            fullResponse += data.content;
                        }
                        if (data.done && data.full_response) {
                            fullResponse = data.full_response;
                        }
                        if (data.error) {
                            throw new Error(data.error);
                        }
                    } catch (e) {
                        // Ignore parse errors for incomplete chunks
                        if (e instanceof SyntaxError) continue;
                        throw e;
                    }
                }
            }
        }

        return {
            user_id: request.user_id,
            session_id: request.session_id,
            response: fullResponse
        };
    } else {
        // Fallback to non-streaming response
        return handleResponse<QueryResponse>(response);
    }
};

const handleTTSStream = async (
    response: Response,
    request: QueryRequest,
    onChunk?: (text: string) => void,
    onAudioChunk?: (audioFilename: string, visemes: VisemeData, sentenceIndex: number) => void
): Promise<QueryTTSResponse> => {
    // Check if it's a streaming response
    const contentType = response.headers.get('content-type');
    if (contentType?.includes('text/event-stream') && (onChunk || onAudioChunk)) {
        // Handle SSE streaming
        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let fullResponse = '';
        let audioChunks: Array<{ filename: string, visemes: VisemeData, index: number }> = [];
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || ''; // Keep incomplete chunk in buffer

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));

                        // Handle text content chunks
                        if (data.content) {
                            onChunk && onChunk(data.content);
                            fullResponse += data.content;
                        }

                        // Handle incremental audio chunks (NEW!)
                        if (data.type === 'audio_chunk' && data.audio_filename && data.visemes) {
                            audioChunks.push({
                                filename: data.audio_filename,
                                visemes: data.visemes,
                                index: data.sentence_index
                            });
                            // Notify about new audio chunk immediately
                            onAudioChunk && onAudioChunk(data.audio_filename, data.visemes, data.sentence_index);
                        }

                        // Handle done event
                        if (data.done) {
                            if (data.full_response) fullResponse = data.full_response;
                        }

                        if (data.error) {
                            throw new Error(data.error);
                        }
                    } catch (e) {
                        // Ignore parse errors for incomplete chunks
                        if (e instanceof SyntaxError) continue;
                        throw e;
                    }
                }
            }
        }

        // Return with all collected audio chunks
        // For compatibility, if we have chunks, use the first one's data in the response
        const firstChunk = audioChunks[0];
        return {
            user_id: request.user_id,
            session_id: request.session_id,
            response: fullResponse,
            audio_filename: firstChunk?.filename,
            visemes: firstChunk?.visemes,
            audio_chunks: audioChunks, // NEW: array of all audio segments
            status: 'success'
        };
    } else {
        // Fallback to non-streaming response
        return handleResponse<QueryTTSResponse>(response);
    }
};

export const queryTTS = async (
    request: QueryRequest,
    signal?: AbortSignal,
    onChunk?: (text: string) => void,
    onAudioChunk?: (audioFilename: string, visemes: VisemeData, sentenceIndex: number) => void
): Promise<QueryTTSResponse> => {
    const response = await authedFetch(`${API_BASE_URL}/query_tts_direct`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(request),
        signal,
    });
    return handleTTSStream(response, request, onChunk, onAudioChunk);
};

export const queryMcpTTS = async (
    request: QueryRequest,
    signal?: AbortSignal,
    onChunk?: (text: string) => void,
    onAudioChunk?: (audioFilename: string, visemes: VisemeData, sentenceIndex: number) => void
): Promise<QueryTTSResponse> => {
    const response = await authedFetch(`${API_BASE_URL}/query_mcp_tts_direct`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(request),
        signal,
    });
    return handleTTSStream(response, request, onChunk, onAudioChunk);
};

export const queryAgentTTS = async (
    request: QueryRequest,
    signal?: AbortSignal,
    onChunk?: (text: string) => void,
    onAudioChunk?: (audioFilename: string, visemes: VisemeData, sentenceIndex: number) => void
): Promise<QueryTTSResponse> => {
    const response = await authedFetch(`${API_BASE_URL}/query_assistant_tts_direct`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(request),
        signal,
    });
    return handleTTSStream(response, request, onChunk, onAudioChunk);
};


const handleFullAgentStream = async (
    response: Response,
    request: FullAgentRequest,
    onChunk?: (text: string) => void,
    onTranscription?: (text: string) => void
): Promise<FullAgentResponse> => {
    // Check if it's a streaming response
    const contentType = response.headers.get('content-type');
    if (contentType?.includes('text/event-stream') && (onChunk || onTranscription)) {
        // Handle SSE streaming
        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let fullResponse = '';
        let audioFilename: string | undefined;
        let visemes: VisemeData | undefined;
        let transcribedText = '';
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || ''; // Keep incomplete chunk in buffer

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));

                        // Handle transcription event (new)
                        if (data.type === 'transcription' && data.text) {
                            transcribedText = data.text;
                            if (onTranscription) onTranscription(data.text);
                        }

                        if (data.content) {
                            onChunk && onChunk(data.content);
                            fullResponse += data.content;
                        }
                        if (data.done) {
                            if (data.full_response) fullResponse = data.full_response;
                            if (data.audio_filename) audioFilename = data.audio_filename;
                            if (data.visemes) visemes = data.visemes;
                            // Update transcribedText if provided in done event (fallback)
                            if (data.text) transcribedText = data.text;
                        }
                        if (data.error) {
                            throw new Error(data.error);
                        }
                    } catch (e) {
                        // Ignore parse errors for incomplete chunks
                        if (e instanceof SyntaxError) continue;
                        throw e;
                    }
                }
            }
        }

        return {
            user_id: request.user_id,
            session_id: request.session_id,
            text: transcribedText,
            response: fullResponse,
            audio_filename: audioFilename || null,
            visemes: visemes!,
            status: 'success'
        };
    } else {
        // Fallback to non-streaming response
        return handleResponse<FullAgentResponse>(response);
    }
};

export const fullAgent = async (
    request: FullAgentRequest,
    signal?: AbortSignal,
    onChunk?: (text: string) => void,
    onTranscription?: (text: string) => void
): Promise<FullAgentResponse> => {
    const formData = new FormData();
    formData.append('file', request.file, 'recording.webm');
    formData.append('user_id', request.user_id);
    formData.append('session_id', request.session_id);
    if (request.system_prompt) {
        formData.append('system_prompt', request.system_prompt);
    }

    const response = await authedFetch(`${API_BASE_URL}/stt_query_tts_direct`, {
        method: 'POST',
        body: formData,
        headers: authHeaders(),
        signal,
    });
    return handleFullAgentStream(response, request, onChunk, onTranscription);
};

export const fullAgentMcp = async (
    request: FullAgentRequest,
    signal?: AbortSignal,
    onChunk?: (text: string) => void,
    onTranscription?: (text: string) => void
): Promise<FullAgentResponse> => {
    const formData = new FormData();
    formData.append('file', request.file, 'recording.webm');
    formData.append('user_id', request.user_id);
    formData.append('session_id', request.session_id);
    if (request.system_prompt) {
        formData.append('system_prompt', request.system_prompt);
    }

    const response = await authedFetch(`${API_BASE_URL}/stt_query_mcp_tts_direct`, {
        method: 'POST',
        body: formData,
        headers: authHeaders(),
        signal,
    });
    return handleFullAgentStream(response, request, onChunk, onTranscription);
};

export const fullAgentAgent = async (
    request: FullAgentRequest,
    signal?: AbortSignal,
    onChunk?: (text: string) => void,
    onTranscription?: (text: string) => void
): Promise<FullAgentResponse> => {
    const formData = new FormData();
    formData.append('file', request.file, 'recording.webm');
    formData.append('user_id', request.user_id);
    formData.append('session_id', request.session_id);
    if (request.system_prompt) {
        formData.append('system_prompt', request.system_prompt);
    }

    const response = await authedFetch(`${API_BASE_URL}/stt_query_assistant_tts_direct`, {
        method: 'POST',
        body: formData,
        headers: authHeaders(),
        signal,
    });
    return handleFullAgentStream(response, request, onChunk, onTranscription);
};

export const uploadDocument = async (request: UploadDocumentRequest, signal?: AbortSignal): Promise<UploadDocumentResponse> => {
    const formData = new FormData();
    formData.append('file', request.file);
    formData.append('user_id', request.user_id);
    formData.append('session_id', request.session_id);
    if (request.target_user_id) {
        formData.append('target_user_id', request.target_user_id);
    }

    // Assuming a new endpoint for document uploads exists on the backend
    const response = await authedFetch(`${API_BASE_URL}/upload_document`, {
        method: 'POST',
        body: formData,
        headers: authHeaders(),
        signal,
    });
    return handleResponse<UploadDocumentResponse>(response);
};

export const listDocuments = async (user_id: string, signal?: AbortSignal, target_user_id?: string): Promise<ListDocumentsResponse> => {
    const url = new URL(`${API_BASE_URL}/list_documents`);
    url.searchParams.set('user_id', user_id);
    if (target_user_id) {
        url.searchParams.set('target_user_id', target_user_id);
    }
    url.searchParams.set('ts', Date.now().toString());
    const response = await authedFetch(url.toString(), { method: 'GET', headers: authHeaders(), signal, cache: 'no-store' });
    return handleResponse<ListDocumentsResponse>(response);
};

export const deleteDocument = async (request: DeleteDocumentRequest, signal?: AbortSignal): Promise<DeleteDocumentResponse> => {
    const url = new URL(`${API_BASE_URL}/delete_document`);
    url.searchParams.set('user_id', request.user_id);
    url.searchParams.set('filename', request.filename);
    if (request.kind) url.searchParams.set('kind', request.kind);
    const response = await authedFetch(url.toString(), { method: 'DELETE', headers: authHeaders(), signal });
    return handleResponse<DeleteDocumentResponse>(response);
};

export const setModel = async (request: SetModelRequest, signal?: AbortSignal): Promise<{ success: boolean }> => {
    const response = await authedFetch(`${API_BASE_URL}/set_model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(request),
        signal,
    });
    return handleResponse<{ success: boolean }>(response);
};

export const setVoice = async (request: SetVoiceRequest, signal?: AbortSignal): Promise<{ success: boolean }> => {
    const response = await authedFetch(`${API_BASE_URL}/set_voice`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(request),
        signal,
    });
    return handleResponse<{ success: boolean }>(response);
};

// --- Session persistence API ---
export const getSessions = async (user_id: string, signal?: AbortSignal): Promise<Session[]> => {
    const url = new URL(`${API_BASE_URL}/sessions`);
    url.searchParams.set('user_id', user_id);
    url.searchParams.set('ts', Date.now().toString());
    const response = await authedFetch(url.toString(), { method: 'GET', headers: authHeaders(), signal, cache: 'no-store' });
    return handleResponse<Session[]>(response);
};

export const createSession = async (request: CreateSessionRequest, signal?: AbortSignal): Promise<Session> => {
    const response = await authedFetch(`${API_BASE_URL}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(request),
        signal,
    });
    return handleResponse<Session>(response);
};

export const renameSession = async (sessionId: string, request: RenameSessionRequest, signal?: AbortSignal): Promise<Session> => {
    const response = await authedFetch(`${API_BASE_URL}/sessions/${sessionId}/rename`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(request),
        signal,
    });
    return handleResponse<Session>(response);
};

export const deleteSession = async (sessionId: string, request: DeleteSessionRequest, signal?: AbortSignal): Promise<{ status: string }> => {
    const response = await authedFetch(`${API_BASE_URL}/sessions/${sessionId}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(request),
        signal,
    });
    return handleResponse<{ status: string }>(response);
};

export const saveSessionMessages = async (sessionId: string, request: SaveMessagesRequest, signal?: AbortSignal): Promise<Session> => {
    const response = await authedFetch(`${API_BASE_URL}/sessions/${sessionId}/messages`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(request),
        signal,
    });
    return handleResponse<Session>(response);
};

export const cancelSession = async (request: CancelRequest): Promise<{ status: string }> => {
    const response = await authedFetch(`${API_BASE_URL}/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(request),
    });
    return handleResponse<{ status: string }>(response);
};

// --- User management API ---
export const listUserStats = async (signal?: AbortSignal): Promise<Array<{ id: string; username: string; role: string; sessions: number; documents: number; mcpTools: number; mcpWebTools: number; mcpLocalTools: number; createdAt: string }>> => {
    const url = new URL(`${API_BASE_URL}/users/stats`);
    // Add cache-busting param to avoid stale data across browsers
    url.searchParams.set('ts', Date.now().toString());
    const response = await authedFetch(url.toString(), { method: 'GET', headers: authHeaders(), signal, cache: 'no-store' });
    return handleResponse<Array<{ id: string; username: string; role: string; sessions: number; documents: number; mcpTools: number; mcpWebTools: number; mcpLocalTools: number; createdAt: string }>>(response);
};

export const createUser = async (username: string, password: string, role: 'admin' | 'user', signal?: AbortSignal): Promise<AdminUser> => {
    const response = await authedFetch(`${API_BASE_URL}/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ username, password, role }),
        signal,
    });
    const u = await handleResponse<{ id: string; username: string; role: string; createdAt: string }>(response);
    // New users have zero sessions/documents initially
    return { id: u.id, name: u.username, role: u.role as 'admin' | 'user', sessions: 0, documents: 0, mcpTools: 0, mcpWebTools: 0, mcpLocalTools: 0, createdAt: u.createdAt };
};

export const updateUser = async (user_id: string, payload: { password?: string; role?: 'admin' | 'user' }, signal?: AbortSignal): Promise<AdminUser> => {
    const response = await authedFetch(`${API_BASE_URL}/users/${user_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(payload),
        signal,
    });
    const u = await handleResponse<{ id: string; username: string; role: string; createdAt: string }>(response);
    // Caller should refresh stats afterward to get counts
    return { id: u.id, name: u.username, role: u.role as 'admin' | 'user', sessions: 0, documents: 0, mcpTools: 0, mcpWebTools: 0, mcpLocalTools: 0, createdAt: u.createdAt };
};

export const deleteUser = async (user_id: string, signal?: AbortSignal): Promise<{ status: string }> => {
    const response = await authedFetch(`${API_BASE_URL}/users/${user_id}`, { method: 'DELETE', headers: authHeaders(), signal });
    return handleResponse<{ status: string }>(response);
};

export const loginUser = async (username: string, password: string, signal?: AbortSignal): Promise<{ user_id: string; session_id: string; username: string; role: string; token?: string }> => {
    const response = await fetch(`${API_BASE_URL}/users/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
        signal,
    });
    return handleResponse<{ user_id: string; session_id: string; username: string; role: string; token?: string }>(response);
};

// --- Admin Configuration API ---
export const getConfig = async (user_id: string, signal?: AbortSignal): Promise<ConfigResponse> => {
    const url = new URL(`${API_BASE_URL}/config`);
    url.searchParams.set('user_id', user_id);
    url.searchParams.set('ts', Date.now().toString());
    const response = await authedFetch(url.toString(), { method: 'GET', headers: authHeaders(), signal, cache: 'no-store' });
    return handleResponse<ConfigResponse>(response);
};

export const updateConfig = async (payload: ConfigUpdateRequest, signal?: AbortSignal): Promise<ConfigResponse> => {
    const response = await authedFetch(`${API_BASE_URL}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(payload),
        signal,
    });
    return handleResponse<ConfigResponse>(response);
};

export const getModelsCatalog = async (user_id: string, signal?: AbortSignal): Promise<ModelsCatalogResponse> => {
    const url = new URL(`${API_BASE_URL}/models`);
    url.searchParams.set('user_id', user_id);
    url.searchParams.set('ts', Date.now().toString());
    const response = await authedFetch(url.toString(), { method: 'GET', headers: authHeaders(), signal, cache: 'no-store' });
    // Backend returns { models: string[] }; normalize to { available_models: string[] }
    const raw = await response.json();
    if (!response.ok) {
        throw new Error(raw?.detail || `Failed to fetch models catalog: ${response.status}`);
    }
    const models = Array.isArray(raw?.models) ? raw.models : [];
    return { available_models: models };
};

export const getModelsLabeledCatalog = async (user_id: string, signal?: AbortSignal): Promise<ModelsCatalogLabeledResponse> => {
    const url = new URL(`${API_BASE_URL}/models_labeled`);
    url.searchParams.set('user_id', user_id);
    url.searchParams.set('ts', Date.now().toString());
    const response = await authedFetch(url.toString(), { method: 'GET', headers: authHeaders(), signal, cache: 'no-store' });
    return handleResponse<ModelsCatalogLabeledResponse>(response);
};

export const getVoicesCatalog = async (user_id: string, signal?: AbortSignal): Promise<VoicesCatalogResponse> => {
    const url = new URL(`${API_BASE_URL}/voices`);
    url.searchParams.set('user_id', user_id);
    url.searchParams.set('ts', Date.now().toString());
    const response = await authedFetch(url.toString(), { method: 'GET', headers: authHeaders(), signal, cache: 'no-store' });
    const raw = await response.json();
    if (!response.ok) {
        throw new Error(raw?.detail || `Failed to fetch voices catalog: ${response.status}`);
    }
    const voices = Array.isArray(raw?.voices) ? raw.voices : [];
    return { available_voices: voices };
};

export const getVoicesLabeledCatalog = async (user_id: string, signal?: AbortSignal): Promise<VoicesCatalogLabeledResponse> => {
    const url = new URL(`${API_BASE_URL}/voices_labeled`);
    url.searchParams.set('user_id', user_id);
    url.searchParams.set('ts', Date.now().toString());
    const response = await fetch(url, { method: 'GET', headers: authHeaders(), signal, cache: 'no-store' });
    return handleResponse<VoicesCatalogLabeledResponse>(response);
};

export const getMcpToolsCatalog = async (user_id: string, signal?: AbortSignal): Promise<McpToolsCatalogResponse> => {
    const url = new URL(`${API_BASE_URL}/mcp_tools`);
    url.searchParams.set('user_id', user_id);
    url.searchParams.set('ts', Date.now().toString());
    const response = await fetch(url, { method: 'GET', headers: authHeaders(), signal, cache: 'no-store' });
    return handleResponse<McpToolsCatalogResponse>(response);
};

export const getMcpStdioCatalog = async (user_id: string, signal?: AbortSignal): Promise<McpStdioToolsCatalogResponse> => {
    const url = new URL(`${API_BASE_URL}/mcp_stdio_tools`);
    url.searchParams.set('user_id', user_id);
    url.searchParams.set('ts', Date.now().toString());
    const response = await fetch(url, { method: 'GET', headers: authHeaders(), signal, cache: 'no-store' });
    return handleResponse<McpStdioToolsCatalogResponse>(response);
};

export const setMcpStdioTools = async (payload: { user_id: string; session_id: string; commands: string[] }, signal?: AbortSignal): Promise<{ success: boolean }> => {
    const response = await authedFetch(`${API_BASE_URL}/set_mcp_stdio_tools`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(payload),
        signal,
    });
    return handleResponse<{ success: boolean }>(response);
};

export const getConfigPath = async (user_id: string, signal?: AbortSignal): Promise<ConfigPathResponse> => {
    const url = new URL(`${API_BASE_URL}/config_path`);
    url.searchParams.set('user_id', user_id);
    url.searchParams.set('ts', Date.now().toString());
    const response = await authedFetch(url.toString(), { method: 'GET', headers: authHeaders(), signal, cache: 'no-store' });
    return handleResponse<ConfigPathResponse>(response);
};

// --- Per-session settings ---
export const getSessionSettings = async (user_id: string, session_id: string, signal?: AbortSignal): Promise<SessionSettingsResponse> => {
    const url = new URL(`${API_BASE_URL}/sessions/${session_id}/settings`);
    url.searchParams.set('user_id', user_id);
    url.searchParams.set('ts', Date.now().toString());
    const response = await authedFetch(url.toString(), { method: 'GET', headers: authHeaders(), signal, cache: 'no-store' });
    return handleResponse<SessionSettingsResponse>(response);
};

// Persist per-user MCP tools selection (multi-select)
export const setMcpTools = async (payload: SetMcpToolsRequest, signal?: AbortSignal): Promise<{ success: boolean }> => {
    const response = await authedFetch(`${API_BASE_URL}/set_mcp_tools`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(payload),
        signal,
    });
    return handleResponse<{ success: boolean }>(response);
};
