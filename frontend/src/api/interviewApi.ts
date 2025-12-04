/**
 * API Service for Interview-Orchestrator Backend
 * Complete implementation of all backend API endpoints
 */

const API_BASE = '/api';

// ==================== Session ID Management ====================

function getOrCreateSessionId(): string {
  let sessionId = localStorage.getItem('interview_session_id');
  if (!sessionId) {
    sessionId = 'session_' + Date.now() + '_' +
        Math.random().toString(36).substring(2, 11);
    localStorage.setItem('interview_session_id', sessionId);
  }
  return sessionId;
}

export function getSessionId(): string {
  return getOrCreateSessionId();
}

export function setSessionId(sessionId: string): void {
  localStorage.setItem('interview_session_id', sessionId);
}

export function resetSessionId(): string {
  const sessionId = 'session_' + Date.now() + '_' +
      Math.random().toString(36).substring(2, 11);
  localStorage.setItem('interview_session_id', sessionId);
  return sessionId;
}

export function getProjectName(): string {
  return localStorage.getItem('interview_project_name') || '';
}

// ==================== Types ====================

export interface ThemeProgress {
  name: string;
  required: number;
  required_filled: number;
  progress_percent: number;
}

export interface Progress {
  current: number;
  total: number;
  percent: number;
  is_complete: boolean;
  themes?: Record<string, ThemeProgress>;
  missing_required?: string[];
}

export interface CompletedRole {
  role: string;
  role_label: string;
  progress_percent: number;
  is_current?: boolean;
}

export interface InterviewStatus {
  phase: string;
  phase_label: string;
  role: string|null;
  role_label: string;
  role_name?: string;
  role_confidence_low?: boolean;
  answered_questions: number;
  uploaded_files_count: number;
  progress?: Progress;
  completed_interviews: number;
  completed_roles: CompletedRole[];
}

export interface Question {
  id: string;
  text: string;
  type?: string;
  field_id?: string;
  theme_name?: string;
}

export interface UploadedFile {
  filename: string;
  filepath?: string;
  size: number;
}

export interface SessionInfo {
  session_id: string;
  session_name?: string;
  role?: string;
  answered_questions: number;
  progress_percent?: number;
  last_activity: string;
  completed_interviews?: number;
  completed_roles?: string[];
}

export interface HistoryEntry {
  question?: string;
  answer?: string;
  type?: string;
  text?: string;
}

export interface LLMBackendStatus {
  current: string;
  local: {available: boolean; model: string;};
  mistral_api: {has_key: boolean; model: string;};
}

// ==================== API Response Types ====================

export interface StartResponse {
  success: boolean;
  question?: Question;
  status?: InterviewStatus;
  message?: string;
}

export interface AnswerResponse {
  success: boolean;
  question?: Question|null;
  status?: InterviewStatus;
  completed?: boolean;
  process_status?: string|null;
  role_classified?: boolean;
}

export interface SessionsResponse {
  success: boolean;
  sessions: SessionInfo[];
}

export interface ResumeSessionResponse {
  success: boolean;
  message?: string;
  question?: Question;
  current_question?: Question;
  history?: HistoryEntry[];
  status?: InterviewStatus;
  session_restored?: boolean;
  answers_count?: number;
}

// ==================== Interview API ====================

/**
 * Start a new interview or resume existing one
 */
export async function startInterview(presetRole?: string):
    Promise<StartResponse> {
  const sessionId = getSessionId();
  const projectName = getProjectName();

  const response = await fetch(`${API_BASE}/start`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      session_id: sessionId,
      preset_role: presetRole,
      session_name: projectName,
    }),
  });

  return response.json();
}

/**
 * Submit an answer and get the next question
 */
export async function submitAnswer(
    questionId: string, answer: string): Promise<AnswerResponse> {
  const sessionId = getSessionId();

  const response = await fetch(`${API_BASE}/answer`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      session_id: sessionId,
      question_id: questionId,
      answer: answer,
    }),
  });

  return response.json();
}

/**
 * Get current interview status
 */
export async function getStatus():
    Promise<{success: boolean; status?: InterviewStatus;}> {
  const sessionId = getSessionId();
  const response = await fetch(`${API_BASE}/status?session_id=${sessionId}`);
  return response.json();
}

/**
 * Get current interview progress
 */
export async function getProgress(): Promise<
    {success: boolean; progress?: Progress; status?: InterviewStatus;}> {
  const sessionId = getSessionId();
  const response = await fetch(`${API_BASE}/progress?session_id=${sessionId}`);
  return response.json();
}

/**
 * Reset the current interview session
 */
export async function resetInterview(): Promise<{
  success: boolean;
  message?: string;
  question?: Question;
  status?: InterviewStatus;
}> {
  const sessionId = getSessionId();

  const response = await fetch(`${API_BASE}/reset`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({session_id: sessionId}),
  });

  return response.json();
}

// ==================== Session Management API ====================

/**
 * Get list of all saved sessions
 */
export async function getSessions(): Promise<SessionsResponse> {
  const response = await fetch(`${API_BASE}/sessions`);
  return response.json();
}

/**
 * Resume a saved session
 */
export async function resumeSession(sessionId: string):
    Promise<ResumeSessionResponse> {
  const response = await fetch(`${API_BASE}/sessions/resume`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({session_id: sessionId}),
  });

  return response.json();
}

/**
 * Delete a saved session
 */
export async function deleteSession(sessionId: string):
    Promise<{success: boolean; message?: string}> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: {'Content-Type': 'application/json'},
  });

  return response.json();
}

/**
 * Save current session manually
 */
export async function saveSession():
    Promise<{success: boolean; message?: string;}> {
  const sessionId = getSessionId();

  const response = await fetch(`${API_BASE}/sessions/save`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({session_id: sessionId}),
  });

  return response.json();
}

// ==================== Multi-Role Interview API ====================

/**
 * Complete the current role interview and save it
 */
export async function completeInterview(): Promise<{
  success: boolean;
  message?: string;
  completed_interview?:
      {role: string; role_label: string; answered_questions: number;};
  total_completed?: number;
}> {
  const sessionId = getSessionId();

  const response = await fetch(`${API_BASE}/interview/complete`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({session_id: sessionId}),
  });

  return response.json();
}

/**
 * Start a new role interview within the same session
 */
export async function startNewRoleInterview(): Promise<{
  success: boolean;
  message?: string;
  question?: Question;
  status?: InterviewStatus;
  completed_interviews?: number;
}> {
  const sessionId = getSessionId();

  const response = await fetch(`${API_BASE}/interview/new`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({session_id: sessionId}),
  });

  return response.json();
}

/**
 * Get all completed interviews
 */
export async function getCompletedInterviews(): Promise<{
  success: boolean;
  completed_interviews?: Array<{
    index: number; role: string; role_label: string; answered_questions: number;
    completed_at?: string;
  }>;
  total?: number;
}> {
  const sessionId = getSessionId();
  const response =
      await fetch(`${API_BASE}/interview/completed?session_id=${sessionId}`);
  return response.json();
}

/**
 * Switch to a specific interview (completed or current)
 */
export async function switchToInterview(interviewIndex: number): Promise<{
  success: boolean;
  message?: string;
  status?: InterviewStatus;
  chat_history?: HistoryEntry[];
  next_question?: Question;
  switched_to?: {role: string; role_label: string; answered_questions: number;};
}> {
  const sessionId = getSessionId();

  const response = await fetch(`${API_BASE}/interview/switch`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      session_id: sessionId,
      interview_index: interviewIndex,
    }),
  });

  return response.json();
}

// ==================== File Upload API ====================

/**
 * Upload a file for the interview
 */
export async function uploadFile(file: File): Promise<{
  success: boolean;
  filename?: string;
  message?: string;
  file?: {filename: string; size: number};
  rag_stats?: Record<string, unknown>;
}> {
  const sessionId = getSessionId();
  const formData = new FormData();
  formData.append('file', file);
  formData.append('session_id', sessionId);

  const response = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    body: formData,
  });

  return response.json();
}

/**
 * Get list of uploaded files
 */
export async function getUploadedFiles(): Promise<{
  success: boolean;
  files?: UploadedFile[];
  rag_stats?: Record<string, unknown>;
}> {
  const sessionId = getSessionId();
  const response = await fetch(`${API_BASE}/files?session_id=${sessionId}`);
  return response.json();
}

/**
 * Delete an uploaded file
 */
export async function deleteFile(filename: string):
    Promise<{success: boolean; message?: string; remaining_files?: number;}> {
  const sessionId = getSessionId();
  const response = await fetch(
      `${API_BASE}/files/${encodeURIComponent(filename)}?session_id=${
          sessionId}`,
      {
        method: 'DELETE',
      });
  return response.json();
}

// ==================== LLM Backend API ====================

/**
 * Get LLM backend status
 */
export async function getLLMStatus():
    Promise<{success: boolean; status?: LLMBackendStatus;}> {
  const sessionId = getSessionId();
  const response =
      await fetch(`${API_BASE}/llm/status?session_id=${sessionId}`);
  return response.json();
}

/**
 * Switch LLM backend
 */
export async function switchLLMBackend(backend: 'local'|'mistral_api'):
    Promise<{success: boolean; message?: string; status?: LLMBackendStatus;}> {
  const sessionId = getSessionId();

  const response = await fetch(`${API_BASE}/llm/switch`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      session_id: sessionId,
      backend: backend,
    }),
  });

  return response.json();
}

// ==================== Export API ====================

/**
 * Export interview as PDF
 */
export async function exportPDF(): Promise<Blob> {
  const sessionId = getSessionId();

  const response = await fetch(`${API_BASE}/export/pdf`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({session_id: sessionId}),
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.message || 'PDF-Generierung fehlgeschlagen');
  }

  return response.blob();
}

/**
 * Get the filename from the Content-Disposition header
 */
export function getFilenameFromResponse(response: Response): string {
  const contentDisposition = response.headers.get('Content-Disposition');
  if (contentDisposition) {
    const match = contentDisposition.match(/filename="(.+)"/);
    if (match) {
      return match[1];
    }
  }
  return 'Prozessdokumentation.pdf';
}
