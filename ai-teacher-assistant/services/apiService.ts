
import { API_BASE_URL } from '../constants';
import { 
    QueryRequest, 
    QueryTTSResponse, 
    FullAgentRequest, 
    FullAgentResponse, 
    QueryResponse, 
    UploadDocumentRequest,
    UploadDocumentResponse
} from '../types';

const handleResponse = async <T,>(response: Response): Promise<T> => {
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error occurred' }));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }
    return response.json() as Promise<T>;
};

export const query = async (request: QueryRequest): Promise<QueryResponse> => {
    const response = await fetch(`${API_BASE_URL}/query_direct`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
    });
    return handleResponse<QueryResponse>(response);
};

export const queryMcp = async (request: QueryRequest): Promise<QueryResponse> => {
    const response = await fetch(`${API_BASE_URL}/query_mcp_direct`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
    });
    return handleResponse<QueryResponse>(response);
};

export const queryTTS = async (request: QueryRequest): Promise<QueryTTSResponse> => {
    const response = await fetch(`${API_BASE_URL}/query_tts_direct`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
    });
    return handleResponse<QueryTTSResponse>(response);
};

export const queryMcpTTS = async (request: QueryRequest): Promise<QueryTTSResponse> => {
    const response = await fetch(`${API_BASE_URL}/query_mcp_tts_direct`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
    });
    return handleResponse<QueryTTSResponse>(response);
};

export const fullAgent = async (request: FullAgentRequest): Promise<FullAgentResponse> => {
    const formData = new FormData();
    formData.append('file', request.file, 'recording.wav');
    formData.append('user_id', request.user_id);
    formData.append('session_id', request.session_id);

    const response = await fetch(`${API_BASE_URL}/stt_query_tts_direct`, {
        method: 'POST',
        body: formData,
    });
    return handleResponse<FullAgentResponse>(response);
};

export const fullAgentMcp = async (request: FullAgentRequest): Promise<FullAgentResponse> => {
    const formData = new FormData();
    formData.append('file', request.file, 'recording.wav');
    formData.append('user_id', request.user_id);
    formData.append('session_id', request.session_id);

    const response = await fetch(`${API_BASE_URL}/stt_query_mcp_tts_direct`, {
        method: 'POST',
        body: formData,
    });
    return handleResponse<FullAgentResponse>(response);
};

export const uploadDocument = async (request: UploadDocumentRequest): Promise<UploadDocumentResponse> => {
    const formData = new FormData();
    formData.append('file', request.file);
    formData.append('user_id', request.user_id);
    formData.append('session_id', request.session_id);

    // Assuming a new endpoint for document uploads exists on the backend
    const response = await fetch(`${API_BASE_URL}/upload_document`, {
        method: 'POST',
        body: formData,
    });
    return handleResponse<UploadDocumentResponse>(response);
};
