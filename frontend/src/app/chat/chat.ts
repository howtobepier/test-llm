import { CdkTextareaAutosize } from '@angular/cdk/text-field';
import { HttpErrorResponse } from '@angular/common/http';
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
  protected draft = '';

  protected send(): void {
    const text = this.draft.trim();
    if (!text || this.loading()) {
      return;
    }

    this.messages.update((current) => [...current, { role: 'user', content: text }]);
    this.draft = '';
    this.loading.set(true);
    this.scrollToBottom();

    this.chatService.send(text).subscribe({
      next: (res) => {
        this.messages.update((current) => [
          ...current,
          { role: 'assistant', content: res.reply },
        ]);
        this.loading.set(false);
        this.scrollToBottom();
      },
      error: (err: HttpErrorResponse) => {
        const detail = this.errorMessage(err);
        this.snackBar.open(detail, 'Chiudi', { duration: 6000 });
        this.messages.update((current) => [
          ...current,
          { role: 'assistant', content: `Errore: ${detail}` },
        ]);
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

  private errorMessage(err: HttpErrorResponse): string {
    const detail = err.error?.detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }
    if (err.status === 0) {
      return 'Backend non raggiungibile. Avvia FastAPI su http://localhost:8000';
    }
    return 'Richiesta fallita. Riprova.';
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
