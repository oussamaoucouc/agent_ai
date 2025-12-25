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
    attachedImages?: string[];    // URLs to uploaded images
    attachedAudio?: string[];     // URLs to uploaded audio files
    attachedVideos?: string[];    // URLs to uploaded videos
    createdAt?: string;           // ISO timestamp for ordering
}

// Media attachment for frontend state management
export interface MediaAttachment {
    id: string;
    file: File;
    type: 'image' | 'audio' | 'video';
    previewUrl?: string;  // For images/videos
}


export type UploadStatus = 'uploading' | 'success' | 'error';

export interface UploadedFile {
    id: string;
    file: File;
    status: UploadStatus;
    kind?: 'pdf' | 'docx' | 'text' | 'csv';
    is_admin_uploaded?: boolean;
    uploaded_by?: string;
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
    role: 'admin' | 'user';
    sessions: number;
    documents: number;
    mcpTools: number;
    mcpWebTools?: number;
    mcpLocalTools?: number;
    createdAt: string;
}

// Complete list of available Kokoro TTS voices
export enum TTSVoice {
    // American Female
    AF_ALLOY = 'af_alloy',
    AF_AOEDE = 'af_aoede',
    AF_BELLA = 'af_bella',
    AF_HEART = 'af_heart',
    AF_JESSICA = 'af_jessica',
    AF_KORE = 'af_kore',
    AF_NICOLE = 'af_nicole',
    AF_NOVA = 'af_nova',
    AF_RIVER = 'af_river',
    AF_SARAH = 'af_sarah',
    AF_SKY = 'af_sky',
    // American Male
    AM_ADAM = 'am_adam',
    AM_ECHO = 'am_echo',
    AM_ERIC = 'am_eric',
    AM_FENRIR = 'am_fenrir',
    AM_LIAM = 'am_liam',
    AM_MICHAEL = 'am_michael',
    AM_ONYX = 'am_onyx',
    AM_PUCK = 'am_puck',
    AM_SANTA = 'am_santa',
    // British Female
    BF_ALICE = 'bf_alice',
    BF_EMMA = 'bf_emma',
    BF_ISABELLA = 'bf_isabella',
    BF_LILY = 'bf_lily',
    // British Male
    BM_DANIEL = 'bm_daniel',
    BM_FABLE = 'bm_fable',
    BM_GEORGE = 'bm_george',
    BM_LEWIS = 'bm_lewis',
    // European Female (Spanish)
    EF_DORA = 'ef_dora',
    // European Male
    EM_ALEX = 'em_alex',
    EM_SANTA = 'em_santa',
    // French Female
    FF_SIWIS = 'ff_siwis',
    // Hindi Female
    HF_ALPHA = 'hf_alpha',
    HF_BETA = 'hf_beta',
    // Hindi Male
    HM_OMEGA = 'hm_omega',
    HM_PSI = 'hm_psi',
    // Italian Female
    IF_SARA = 'if_sara',
    // Italian Male
    IM_NICOLA = 'im_nicola',
    // Japanese Female
    JF_ALPHA = 'jf_alpha',
    JF_GONGITSUNE = 'jf_gongitsune',
    JF_NEZUMI = 'jf_nezumi',
    JF_TEBUKURO = 'jf_tebukuro',
}


// API Request/Response types based on FastAPI backend

export interface QueryRequest {
    user_id: string;
    session_id: string;
    query: string;
    system_prompt?: string;
    images?: string[]; // Base64 encoded images
    audio?: string[];  // Base64 encoded audio
    videos?: string[]; // Base64 encoded videos
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
    audio_chunks?: Array<{ filename: string, visemes: VisemeData, index: number }>; // NEW: Incremental audio segments
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
    target_user_id?: string;
}

export interface UploadDocumentResponse {
    message: string;
    filename: string;
    path?: string;
    duplicate?: boolean;
    kind?: 'pdf' | 'docx' | 'text' | 'csv';
}

export interface DeleteDocumentRequest {
    user_id: string;
    filename: string;
    kind?: 'pdf' | 'docx' | 'text' | 'csv';
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
    documents: {
        filename: string;
        path: string;
        kind?: 'pdf' | 'docx' | 'text' | 'csv';
        is_admin_uploaded?: boolean;
        uploaded_by?: string;
    }[];
}

// --- Admin Configuration types ---
export interface ConfigResponse {
    model: string;
    voice: string;
    ollama_base_url: string;
    openai_base_url?: string;
    openai_api_key_set: boolean;
    google_api_key_set: boolean;
    openrouter_api_key_set: boolean;
    agno_api_key_set: boolean;
    gemini_search_enabled: boolean;
    mcp_transport: string;
    mcp_server_url?: string | null;
    mcp_stdio_command?: string | null;
    mcp_stdio_args: string[];
    mcp_stdio_commands: string[];
    mcp_stdio_tools?: { label: string; command: string }[];
    available_models_labeled?: { label: string; id: string; provider?: string; supports_images?: boolean; supports_audio?: boolean; supports_videos?: boolean }[];
    available_models: string[];
    available_voices_labeled?: { label: string; id: string }[];
    available_voices: string[];
    mcp_servers: { label: string; url: string; is_autonomous?: boolean }[];
}

export interface ConfigUpdateRequest {
    user_id: string;
    model?: string;
    voice?: string;
    ollama_base_url?: string;
    openai_base_url?: string;
    openai_api_key?: string | null;
    google_api_key?: string | null;
    openrouter_api_key?: string | null;
    agno_api_key?: string | null;
    gemini_search_enabled?: boolean;
    mcp_transport?: string;
    mcp_server_url?: string | null;
    mcp_stdio_command?: string | null;
    mcp_stdio_args?: string[];
    mcp_stdio_commands?: string[];
    mcp_stdio_tools?: { label: string; command: string }[];
    available_models_labeled?: { label: string; id: string; provider?: string; supports_images?: boolean; supports_audio?: boolean; supports_videos?: boolean }[];
    available_models?: string[];
    available_voices_labeled?: { label: string; id: string }[];
    available_voices?: string[];
    mcp_servers?: { label: string; url: string; is_autonomous?: boolean }[];
}

export interface ModelsCatalogResponse {
    available_models: string[];
}

export interface VoicesCatalogResponse {
    available_voices: string[];
}

export interface LabeledItem {
    label: string;
    id: string;
    provider?: string;
    supports_images?: boolean;
    supports_audio?: boolean;
    supports_videos?: boolean;
}

export interface ModelsCatalogLabeledResponse {
    items: LabeledItem[];
}

export interface VoicesCatalogLabeledResponse {
    items: LabeledItem[];
}

// MCP tools catalog types (admin-configured label + URL)
export interface McpToolItem {
    label: string;
    url: string;
    is_autonomous?: boolean;
}

export interface McpToolsCatalogResponse {
    tools: McpToolItem[];
}

export interface McpStdioItem {
    label: string;
    command: string;
}

export interface McpStdioToolsCatalogResponse {
    tools: McpStdioItem[];
}

// Set MCP tools selection for a user (multi-select)
export interface SetMcpToolsRequest {
    user_id: string;
    session_id: string;
    tool_labels?: string[]; // labels to resolve to URLs (backend expects 'tool_labels')
    tool_urls?: string[];   // explicit URLs if provided
}

export interface ConfigPathResponse {
    config_state_path: string;
    exists: boolean;
}

// --- Per-session settings ---
export interface SessionSettingsResponse {
    model_id: string;
    voice: string; // matches TTSVoice enum string values
    mcp_tools_urls: string[]; // selected MCP tool URLs for this user/session
    mcp_stdio_commands: string[]; // selected stdio MCP commands for this user/session
}
