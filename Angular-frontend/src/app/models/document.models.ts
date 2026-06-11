export interface DocumentTag {
  key: string;
  value: string;
}

export interface UploadMetadata {
  clientId: string;
  userId: string;
  fileType: string;
  fileSubType?: string;
  docType?: string;
  stage?: string;
  parentFolder?: string;
  uploadedBy?: string;
  description?: string;
  linked: boolean;
  tags: DocumentTag[];
}

export interface UploadInitResponse {
  fileId: string;
  uploadUrl: string;
  s3Key: string;
  expiresIn: number;
  metadata: DocumentFile;
}

export interface UploadResult {
  fileId: string;
  s3Key: string;
  metadata: DocumentFile;
}

export interface DocumentFile {
  fileId: string;
  fileName: string;
  clientId: string;
  userId: string;
  fileType: string;
  fileSubType: string;
  docType: string;
  stage: string;
  uploadedBy: string;
  parentFolder: string;
  description: string;
  tags: DocumentTag[];
  linked: boolean;
  mimeType: string;
  extension: string;
  fileSize: number;
  s3Key: string;
  s3Bucket: string;
  uploadStatus: string;
  createdAt: string;
  lastUpdatedAt: string;
}

export interface DocumentFolder {
  name: string;
  path: string;
  fileCount: number;
}

export interface Breadcrumb {
  name: string;
  path: string;
}

export interface ListFolderResponse {
  requestType: 'list-folder';
  clientId: string;
  currentFolder: string;
  breadcrumbs: Breadcrumb[];
  folders: DocumentFolder[];
  files: DocumentFile[];
  scanned?: {
    pages: number;
    hasMore: boolean;
    note?: string;
  };
}

export interface FileViewResponse {
  requestType: 'get-file';
  file: DocumentFile;
  viewUrl: string;
  expiresIn: number;
}

export type QueryMode = 'hybrid' | 'semantic';

export interface ChatHistoryMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface QueryRequest {
  question: string;
  history?: ChatHistoryMessage[];
  top_k?: number;
  client_id?: string;
  file_id?: string;
  min_similarity?: number;
  use_query_planner: boolean;
  use_query_rewrite: boolean;
  max_rewrites: number;
}

export interface HybridQueryRequest extends QueryRequest {
  semantic_weight: number;
  keyword_weight: number;
}

export interface Citation {
  citation_id: number;
  chunk_id: string;
  file_id: string;
  filename: string;
  page_start: number | null;
  page_end: number | null;
  chunk_index: number;
  similarity: number;
  vector_similarity?: number | null;
  keyword_score?: number | null;
  hybrid_score?: number | null;
  content: string;
  metadata: Record<string, unknown>;
}

export interface QueryResponse {
  answer: string;
  used_retrieval: boolean;
  insufficient_evidence: boolean;
  citations: Citation[];
  rewritten_queries: string[];
  intent?: string | null;
  answer_style?: string | null;
  policy_warning?: string | null;
  hallucination_warning?: string | null;
  unsupported_claims: string[];
}
