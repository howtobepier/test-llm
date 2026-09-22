import { CdkTextareaAutosize } from '@angular/cdk/text-field';
import {
  Component,
  ElementRef,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatMiniFabButton } from '@angular/material/button';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatToolbar } from '@angular/material/toolbar';
import { ChatMessage, ChatService } from '../services/chat';

@Component({
  selector: 'app-chat',
  imports: [
    FormsModule,
    MatToolbar,
    MatIcon,
    MatProgressBar,
    MatFormField,
    MatLabel,
    MatInput,
    MatMiniFabButton,
    CdkTextareaAutosize,
  ],
  templateUrl: './chat.html',
  styleUrl: './chat.scss',
})
export class Chat {
  private readonly chatService = inject(ChatService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly scroller = viewChild<ElementRef<HTMLElement>>('scroller');

  protected readonly messages = signal<ChatMessage[]>([]);
  protected readonly loading = signal(false);
  /** True finché non arriva il primo token dello stream. */
  protected readonly waitingFirstToken = signal(false);
  protected draft = '';

  protected send(): void {
    const text = this.draft.trim();
    if (!text || this.loading()) {
      return;
    }

    this.messages.update((current) => [...current, { role: 'user', content: text }]);
    this.draft = '';
    this.loading.set(true);
    this.waitingFirstToken.set(true);
    this.scrollToBottom();

    this.chatService.stream(text).subscribe({
      next: (event) => {
        if (event.type === 'token') {
          const isFirst = this.waitingFirstToken();
          if (isFirst) {
            this.waitingFirstToken.set(false);
          }
          this.messages.update((current) => {
            if (isFirst) {
              return [...current, { role: 'assistant', content: event.token }];
            }
            const next = current.slice();
            const last = next[next.length - 1];
            next[next.length - 1] = {
              role: 'assistant',
              content: last.content + event.token,
            };
            return next;
          });
          this.scrollToBottom();
          return;
        }

        if (event.type === 'error') {
          this.snackBar.open(event.message, 'Chiudi', { duration: 6000 });
          this.messages.update((current) => {
            const last = current[current.length - 1];
            if (!this.waitingFirstToken() && last?.role === 'assistant') {
              const next = current.slice();
              next[next.length - 1] = {
                role: 'assistant',
                content: `Errore: ${event.message}`,
              };
              return next;
            }
            return [...current, { role: 'assistant', content: `Errore: ${event.message}` }];
          });
          this.waitingFirstToken.set(false);
          this.loading.set(false);
          this.scrollToBottom();
          return;
        }

        // done
        this.waitingFirstToken.set(false);
        this.loading.set(false);
        this.scrollToBottom();
      },
      error: () => {
        const detail = 'Richiesta fallita. Riprova.';
        this.snackBar.open(detail, 'Chiudi', { duration: 6000 });
        this.messages.update((current) => [
          ...current,
          { role: 'assistant', content: `Errore: ${detail}` },
        ]);
        this.waitingFirstToken.set(false);
        this.loading.set(false);
        this.scrollToBottom();
      },
    });
  }

  protected onEnter(event: Event): void {
    const keyboardEvent = event as KeyboardEvent;
    if (keyboardEvent.shiftKey) {
      return;
    }
    keyboardEvent.preventDefault();
    this.send();
  }

  private scrollToBottom(): void {
    queueMicrotask(() => {
      const el = this.scroller()?.nativeElement;
      if (el) {
        el.scrollTop = el.scrollHeight;
      }
    });
  }
}
