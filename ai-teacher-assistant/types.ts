
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


// API Request/Response types based on FastAPI backend

export interface QueryRequest {
    user_id: string;
    session_id: string;
    query: string;
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
}