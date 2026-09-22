import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, Observer } from 'rxjs';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  reply: string;
}

export type ChatStreamEvent =
  | { type: 'token'; token: string }
  | { type: 'done' }
  | { type: 'error'; message: string };

@Injectable({
  providedIn: 'root',
})
export class ChatService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = 'http://localhost:8000';

  send(message: string): Observable<ChatResponse> {
    return this.http.post<ChatResponse>(`${this.baseUrl}/chat`, { message });
  }

  /** Stream SSE da POST /chat/stream: token incrementali fino a done/error. */
  stream(message: string): Observable<ChatStreamEvent> {
    return new Observable((subscriber: Observer<ChatStreamEvent>) => {
      const controller = new AbortController();

      void (async () => {
        try {
          const response = await fetch(`${this.baseUrl}/chat/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
            body: JSON.stringify({ message }),
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
              // ignora body non JSON
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
            if (done) {
              break;
            }
            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split('\n\n');
            buffer = parts.pop() ?? '';

            for (const part of parts) {
              const dataLine = part
                .split('\n')
                .map((line) => line.trimEnd())
                .find((line) => line.startsWith('data:'));
              if (!dataLine) {
                continue;
              }
              const raw = dataLine.slice(5).trim();
              if (!raw) {
                continue;
              }

              let payload: { token?: string; done?: boolean; error?: string };
              try {
                payload = JSON.parse(raw) as {
                  token?: string;
                  done?: boolean;
                  error?: string;
                };
              } catch {
                continue;
              }

              if (typeof payload.error === 'string') {
                subscriber.next({ type: 'error', message: payload.error });
                subscriber.complete();
                return;
              }
              if (payload.done) {
                subscriber.next({ type: 'done' });
                subscriber.complete();
                return;
              }
              if (typeof payload.token === 'string' && payload.token.length > 0) {
                subscriber.next({ type: 'token', token: payload.token });
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
          const message =
            err instanceof TypeError
              ? 'Backend non raggiungibile. Avvia FastAPI su http://localhost:8000'
              : err instanceof HttpErrorResponse
                ? this.httpErrorMessage(err)
                : 'Richiesta fallita. Riprova.';
          subscriber.next({ type: 'error', message });
          subscriber.complete();
        }
      })();

      return () => controller.abort();
    });
  }

  private httpErrorMessage(err: HttpErrorResponse): string {
    const detail = err.error?.detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }
    if (err.status === 0) {
      return 'Backend non raggiungibile. Avvia FastAPI su http://localhost:8000';
    }
    return 'Richiesta fallita. Riprova.';
  }
}
