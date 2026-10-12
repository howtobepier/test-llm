import { Pipe, PipeTransform } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

/** Escape HTML e render Markdown base senza eseguire markup non attendibile. */
@Pipe({ name: 'safeMarkdown', standalone: true })
export class SafeMarkdownPipe implements PipeTransform {
  constructor(private readonly sanitizer: DomSanitizer) {}

  transform(value: string | null | undefined): SafeHtml {
    const raw = value ?? '';
    const escaped = this.escape(raw);
    const html = this.render(escaped);
    return this.sanitizer.bypassSecurityTrustHtml(html);
  }

  private escape(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  private render(text: string): string {
    const lines = text.split('\n');
    const out: string[] = [];
    let inUl = false;
    let inOl = false;
    let inCode = false;
    let codeBuf: string[] = [];

    const closeLists = () => {
      if (inUl) {
        out.push('</ul>');
        inUl = false;
      }
      if (inOl) {
        out.push('</ol>');
        inOl = false;
      }
    };

    for (const line of lines) {
      if (line.startsWith('```')) {
        if (inCode) {
          out.push(`<pre class="md-code"><code>${codeBuf.join('\n')}</code></pre>`);
          codeBuf = [];
          inCode = false;
        } else {
          closeLists();
          inCode = true;
        }
        continue;
      }
      if (inCode) {
        codeBuf.push(line);
        continue;
      }

      const heading = /^(#{1,3})\s+(.+)$/.exec(line);
      if (heading) {
        closeLists();
        const level = heading[1].length;
        out.push(`<h${level} class="md-h">${this.inline(heading[2])}</h${level}>`);
        continue;
      }

      const ul = /^[-*]\s+(.+)$/.exec(line);
      if (ul) {
        if (inOl) {
          out.push('</ol>');
          inOl = false;
        }
        if (!inUl) {
          out.push('<ul class="md-list">');
          inUl = true;
        }
        out.push(`<li>${this.inline(ul[1])}</li>`);
        continue;
      }

      const ol = /^(\d+)\.\s+(.+)$/.exec(line);
      if (ol) {
        if (inUl) {
          out.push('</ul>');
          inUl = false;
        }
        if (!inOl) {
          out.push('<ol class="md-list">');
          inOl = true;
        }
        out.push(`<li>${this.inline(ol[2])}</li>`);
        continue;
      }

      if (!line.trim()) {
        closeLists();
        out.push('<div class="md-gap"></div>');
        continue;
      }

      closeLists();
      out.push(`<p class="md-p">${this.inline(line)}</p>`);
    }

    if (inCode) {
      out.push(`<pre class="md-code"><code>${codeBuf.join('\n')}</code></pre>`);
    }
    closeLists();
    return out.join('');
  }

  private inline(text: string): string {
    return text
      .replace(/`([^`]+)`/g, '<code class="md-inline">$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      .replace(
        /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
      );
  }
}
