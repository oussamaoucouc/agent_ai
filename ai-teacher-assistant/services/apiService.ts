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
    SaveMessagesRequest
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
    const response = await fetch(url, { method: 'GET', signal });
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
    const response = await fetch(url, { method: 'GET', signal });
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
