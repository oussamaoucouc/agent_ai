export type QueryMode = 'agent' | 'direct' | 'tools';

export enum User {
    USER = 'user',
    ASSISTANT = 'assistant',
}

export interface MouthCue {
    start: number; // in seconds
    end: number;   // in seconds
    value: string; // e.g., 'A', 'B', 'X'
}

export interface VisemeData {
    metadata: {
        soundFile: string;
        duration: number;
    };
    mouthCues: MouthCue[];
}

export interface Message {
    id: string;
    text: string;
    sender: User;
    audioUrl?: string;
    visemes?: VisemeData;
}

export type UploadStatus = 'uploading' | 'success' | 'error';

export interface UploadedFile {
    id: string;
    file: File;
    status: UploadStatus;
}

export interface Session {
    id: string;
    name: string;
    messages: Message[];
    createdAt: string; 
}

// Data type for the admin dashboard user list
export interface AdminUser {
    id: string;
    name: string;
    sessions: number;
    documents: number;
    createdAt: string;
}

// Updated voices from Kokoro TTS documentation
export enum TTSVoice {
    AF_BELLA = 'af_bella',
    AF_NICOLE = 'af_nicole',
    AF_SARAH = 'af_sarah',
    AF_SKY = 'af_sky',
    BF_EMMA = 'bf_emma',
    BF_ISABELLA = 'bf_isabella',
    AM_ADAM = 'am_adam',
    AM_MICHAEL = 'am_michael',
    BM_GEORGE = 'bm_george',
    BM_LEWIS = 'bm_lewis',
}


// API Request/Response types based on FastAPI backend

export interface QueryRequest {
    user_id: string;
    session_id: string;
    query: string;
    system_prompt?: string;
}

export interface QueryResponse {
    user_id: string;
    session_id: string;
    response: string;
}

export interface QueryTTSResponse {
    user_id: string;
    session_id: string;
    response: string;
    audio_filename: string | null;
    visemes: VisemeData;
    status: string;
}

export interface FullAgentRequest {
    file: Blob;
    user_id: string;
    session_id: string;
    system_prompt?: string;
}

export interface FullAgentResponse {
    text: string;
    response: string;
    audio_filename: string | null;
    visemes: VisemeData;
    user_id: string;
    session_id: string;
    status: string;
}

export interface UploadDocumentRequest {
    file: File;
    user_id: string;
    session_id: string;
}

export interface UploadDocumentResponse {
    message: string;
    filename: string;
    path?: string;
}

export interface DeleteDocumentRequest {
    user_id: string;
    filename: string;
}

export interface DeleteDocumentResponse {
    message: string;
    filename: string;
}

export interface SetModelRequest {
    user_id: string;
    session_id: string;
    model: string;
}

export interface SetVoiceRequest {
    user_id: string;
    session_id: string;
    voice: TTSVoice;
}

// Cancel active generation/request
export interface CancelRequest {
    user_id: string;
    session_id: string;
}

// Server session API types
export interface CreateSessionRequest {
    user_id: string;
}

export interface RenameSessionRequest {
    user_id: string;
    name: string;
}

export interface DeleteSessionRequest {
    user_id: string;
}

export interface SaveMessagesRequest {
    user_id: string;
    messages: Message[];
}

// List documents response for persisted user PDFs
export interface ListDocumentsResponse {
    documents: { filename: string; path: string }[];
}