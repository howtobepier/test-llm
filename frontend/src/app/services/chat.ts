import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, Observer, TimeoutError, catchError, map, of, timeout } from 'rxjs';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  mode?: string;
  usedModel?: boolean;
  sources?: string[];
  at?: number;
}

export interface ChatResponse {
  reply: string;
  mode?: string;
  used_model?: boolean;
  tool?: string | null;
  tool_ok?: boolean | null;
  sources?: string[];
  data?: Record<string, unknown>;
}

export type ChatStreamEvent =
  | { type: 'request_id'; requestId: string }
  | {
      type: 'meta';
      mode: string;
      used_model: boolean;
      tool?: string;
      tool_ok?: boolean;
      sources?: string[];
    }
  | { type: 'token'; token: string }
  | {
      type: 'done';
      mode?: string;
      used_model?: boolean;
      sources?: string[];
      tool?: string;
      tool_ok?: boolean;
    }
  | { type: 'error'; message: string };

export interface NoteHit {
  path: string;
  relative?: string;
  title: string;
  tags?: string[];
  snippet?: string;
  mtime?: number;
}

export interface TodoItem {
  id: string;
  title: string;
  priority: number;
  due_at?: string | null;
  done: boolean;
  created_at?: string;
  completed_at?: string | null;
}

export interface AgendaItem {
  id?: string;
  title: string;
  starts_at: string;
  ends_at?: string | null;
  notes?: string | null;
}

export interface ReminderItem {
  id?: string;
  title: string;
  due_at: string;
  done?: boolean;
}

export interface RoutineItem {
  id: string;
  name?: string;
  hour?: number;
  minute?: number;
  enabled?: boolean;
  action?: string;
  when?: string;
}

export interface ActionLogItem {
  created_at?: string;
  kind?: string;
  status: string;
  summary: string;
  detail?: string | null;
}

export interface DashboardData {
  backend?: { ok: boolean; host?: string };
  model: Record<string, unknown>;
  voice?: {
    stt?: Record<string, unknown>;
    tts?: Record<string, unknown>;
  };
  todos: TodoItem[];
  priorities?: TodoItem[];
  agenda: AgendaItem[];
  reminders: ReminderItem[];
  routines?: RoutineItem[];
  upcoming_routines: RoutineItem[];
  recent_notes?: NoteHit[];
  notifications: Array<Record<string, unknown>>;
  recent_actions: ActionLogItem[];
  integrations: Record<string, string>;
  settings: Record<string, unknown>;
}

export interface SystemInfo {
  cpu_percent: number;
  cpu_cores: number;
  ram_percent: number;
  ram_total_gb: number;
  disk_percent: number;
  disk_free_gb: number;
  host: string;
  os: string;
}

export type PanelState = 'idle' | 'loading' | 'ready' | 'empty' | 'error' | 'unconfigured';

@Injectable({
  providedIn: 'root',
})
export class ChatService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = 'http://127.0.0.1:8000';
  private readonly defaultTimeoutMs = 30000;

  health(): Observable<{ ok: boolean; detail?: string }> {
    return this.http.get<{ status?: string }>(`${this.baseUrl}/statu-model-server`).pipe(
      timeout(4000),
      map((r) => ({ ok: r?.status === 'ok' })),
      catchError((err) => of({ ok: false, detail: this.errorMessage(err) })),
    );
  }

  status(): Observable<Record<string, unknown>> {
    return this.http.get<Record<string, unknown>>(`${this.baseUrl}/api/status`).pipe(
      timeout(this.defaultTimeoutMs),
    );
  }

  system(): Observable<SystemInfo> {
    return this.http.get<SystemInfo>(`${this.baseUrl}/api/system`).pipe(timeout(4000));
  }

  dashboard(): Observable<DashboardData> {
    return this.http.get<DashboardData>(`${this.baseUrl}/api/dashboard`).pipe(
      timeout(this.defaultTimeoutMs),
    );
  }

  send(message: string, history: ChatMessage[] = []): Observable<ChatResponse> {
    return this.http.post<ChatResponse>(`${this.baseUrl}/chat`, {
      message,
      history: history.map((m) => ({ role: m.role, content: m.content })),
    });
  }

  searchNotes(q: string): Observable<{ results: NoteHit[] }> {
    return this.http
      .get<{ results: NoteHit[] }>(`${this.baseUrl}/api/notes/search`, { params: { q } })
      .pipe(timeout(this.defaultTimeoutMs));
  }

  recentNotes(limit = 8): Observable<{ results: NoteHit[] }> {
    return this.http
      .get<{ results: NoteHit[] }>(`${this.baseUrl}/api/notes/recent`, {
        params: { limit: String(limit) },
      })
      .pipe(timeout(this.defaultTimeoutMs));
  }

  saveNote(title: string, body: string, folder = 'raw', tags: string[] = []): Observable<Record<string, unknown>> {
    return this.http
      .post<Record<string, unknown>>(`${this.baseUrl}/api/notes`, { title, body, folder, tags })
      .pipe(timeout(this.defaultTimeoutMs));
  }

  openNote(path: string): Observable<Record<string, unknown>> {
    return this.http
      .get<Record<string, unknown>>(`${this.baseUrl}/api/notes/open`, { params: { path } })
      .pipe(timeout(this.defaultTimeoutMs));
  }

  listTodos(): Observable<{ todos: TodoItem[] }> {
    return this.http
      .get<{ todos: TodoItem[] }>(`${this.baseUrl}/api/todos`)
      .pipe(timeout(this.defaultTimeoutMs));
  }

  addTodo(title: string, priority = 2, due_at?: string | null): Observable<Record<string, unknown>> {
    return this.http
      .post<Record<string, unknown>>(`${this.baseUrl}/api/todos`, { title, priority, due_at })
      .pipe(timeout(this.defaultTimeoutMs));
  }

  completeTodo(titleOrId: string): Observable<Record<string, unknown>> {
    return this.http
      .post<Record<string, unknown>>(`${this.baseUrl}/api/todos/complete`, {
        title_or_id: titleOrId,
      })
      .pipe(timeout(this.defaultTimeoutMs));
  }

  listAgenda(day?: string): Observable<{ events: AgendaItem[] }> {
    const opts = day ? { params: { day } } : {};
    return this.http
      .get<{ events: AgendaItem[] }>(`${this.baseUrl}/api/agenda`, opts)
      .pipe(timeout(this.defaultTimeoutMs));
  }

  listReminders(): Observable<{ reminders: ReminderItem[] }> {
    return this.http
      .get<{ reminders: ReminderItem[] }>(`${this.baseUrl}/api/reminders`)
      .pipe(timeout(this.defaultTimeoutMs));
  }

  listRoutines(): Observable<{ routines: RoutineItem[]; upcoming: RoutineItem[] }> {
    return this.http
      .get<{ routines: RoutineItem[]; upcoming: RoutineItem[] }>(`${this.baseUrl}/api/routines`)
      .pipe(timeout(this.defaultTimeoutMs));
  }

  runRoutine(routineId: string): Observable<{
    ok: boolean;
    summary: string;
    data?: unknown;
    error?: string;
  }> {
    return this.http
      .post<{ ok: boolean; summary: string; data?: unknown; error?: string }>(
        `${this.baseUrl}/api/routines/${encodeURIComponent(routineId)}/run`,
        {},
      )
      .pipe(timeout(60000));
  }

  briefing(): Observable<{ ok: boolean; summary: string; data?: Record<string, unknown> }> {
    return this.http
      .post<{ ok: boolean; summary: string; data?: Record<string, unknown> }>(
        `${this.baseUrl}/api/briefing`,
        {},
      )
      .pipe(timeout(30000));
  }

  eveningSummary(): Observable<{ ok: boolean; summary: string; data?: Record<string, unknown> }> {
    return this.http
      .post<{ ok: boolean; summary: string; data?: Record<string, unknown> }>(
        `${this.baseUrl}/api/evening-summary`,
        {},
      )
      .pipe(timeout(30000));
  }

  planToday(): Observable<{ ok: boolean; summary: string; data?: Record<string, unknown> }> {
    return this.http
      .post<{ ok: boolean; summary: string; data?: Record<string, unknown> }>(
        `${this.baseUrl}/api/priorities`,
        {},
      )
      .pipe(timeout(this.defaultTimeoutMs));
  }

  cancel(requestId: string): Observable<{ ok: boolean }> {
    return this.http.post<{ ok: boolean }>(`${this.baseUrl}/chat/cancel`, { request_id: requestId });
  }

  transcribe(blob: Blob, filename = 'audio.webm'): Observable<{ text: string; ok?: boolean }> {
    const form = new FormData();
    form.append('file', blob, filename);
    return this.http
      .post<{ text: string; ok?: boolean }>(`${this.baseUrl}/api/voice/transcribe`, form)
      .pipe(timeout(120000));
  }

  speak(text: string): Observable<Blob> {
    return this.http
      .post(`${this.baseUrl}/api/voice/speak`, { text }, { responseType: 'blob' })
      .pipe(timeout(60000));
  }

  stopSpeak(): Observable<{ ok: boolean }> {
    return this.http.post<{ ok: boolean }>(`${this.baseUrl}/api/voice/stop`, {});
  }

  stream(message: string, history: ChatMessage[] = []): Observable<ChatStreamEvent> {
    return new Observable((subscriber: Observer<ChatStreamEvent>) => {
      const controller = new AbortController();

      void (async () => {
        try {
          const response = await fetch(`${this.baseUrl}/chat/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
            body: JSON.stringify({
              message,
              history: history.map((m) => ({ role: m.role, content: m.content })),
            }),
            signal: controller.signal,
          });

          if (!response.ok) {
            let detail = `Richiesta fallita (${response.status}).`;
            try {
              const payload = (await response.json()) as { detail?: unknown };
              if (typeof payload.detail === 'string' && payload.detail.trim()) {
                detail = payload.detail;
              }
            } catch {
              // ignora
            }
            subscriber.next({ type: 'error', message: detail });
            subscriber.complete();
            return;
          }

          if (!response.body) {
            subscriber.next({ type: 'error', message: 'Risposta senza body dallo stream.' });
            subscriber.complete();
            return;
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split('\n\n');
            buffer = parts.pop() ?? '';

            for (const part of parts) {
              const dataLine = part
                .split('\n')
                .map((line) => line.trimEnd())
                .find((line) => line.startsWith('data:'));
              if (!dataLine) continue;
              const raw = dataLine.slice(5).trim();
              if (!raw) continue;

              let payload: Record<string, unknown>;
              try {
                payload = JSON.parse(raw) as Record<string, unknown>;
              } catch {
                continue;
              }

              if (typeof payload['request_id'] === 'string') {
                subscriber.next({ type: 'request_id', requestId: payload['request_id'] });
                continue;
              }
              if (payload['type'] === 'meta') {
                subscriber.next({
                  type: 'meta',
                  mode: String(payload['mode'] ?? ''),
                  used_model: Boolean(payload['used_model']),
                  tool: payload['tool'] as string | undefined,
                  tool_ok: payload['tool_ok'] as boolean | undefined,
                  sources: payload['sources'] as string[] | undefined,
                });
                continue;
              }
              if (payload['type'] === 'error' || typeof payload['error'] === 'string') {
                subscriber.next({
                  type: 'error',
                  message: String(payload['message'] ?? payload['error'] ?? 'Errore'),
                });
                subscriber.complete();
                return;
              }
              if (payload['type'] === 'done' || payload['done'] === true) {
                subscriber.next({
                  type: 'done',
                  mode: payload['mode'] as string | undefined,
                  used_model: payload['used_model'] as boolean | undefined,
                  sources: payload['sources'] as string[] | undefined,
                  tool: payload['tool'] as string | undefined,
                  tool_ok: payload['tool_ok'] as boolean | undefined,
                });
                subscriber.complete();
                return;
              }
              if (payload['type'] === 'token' || typeof payload['token'] === 'string') {
                const token = String(payload['token'] ?? '');
                if (token) subscriber.next({ type: 'token', token });
              }
            }
          }

          subscriber.next({ type: 'done' });
          subscriber.complete();
        } catch (err) {
          if (controller.signal.aborted) {
            subscriber.complete();
            return;
          }
          subscriber.next({ type: 'error', message: this.errorMessage(err) });
          subscriber.complete();
        }
      })();

      return () => controller.abort();
    });
  }

  errorMessage(err: unknown): string {
    if (err instanceof TimeoutError) {
      return 'Timeout: il backend non ha risposto in tempo.';
    }
    if (err instanceof HttpErrorResponse) {
      const detail = err.error?.detail;
      if (typeof detail === 'string' && detail.trim()) return detail;
      if (err.status === 0) {
        return 'Backend non raggiungibile su http://127.0.0.1:8000';
      }
      return `Errore HTTP ${err.status || '?'}`.trim();
    }
    if (err instanceof TypeError) {
      return 'Backend non raggiungibile su http://127.0.0.1:8000';
    }
    if (err instanceof Error && err.message) return err.message;
    return 'Richiesta fallita. Riprova.';
  }
}
