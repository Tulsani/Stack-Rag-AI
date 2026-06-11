import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import {
  ChatHistoryMessage,
  DocumentFile,
  HybridQueryRequest,
  QueryMode,
  QueryRequest,
  QueryResponse
} from '../../models/document.models';
import { QueryEngineService } from '../../services/query-engine.service';

interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
  renderedAnswer?: string;
  responses?: QueryResponse[];
}

@Component({
  selector: 'app-chat-panel',
  imports: [CommonModule, FormsModule],
  templateUrl: './chat-panel.component.html',
  styleUrl: './chat-panel.component.scss'
})
export class ChatPanelComponent {
  private static readonly chatHistoryLimit = 3;

  @Input() clientId = '';
  @Input() selectedFiles: DocumentFile[] = [];
  @Output() closed = new EventEmitter<void>();

  messages: ChatMessage[] = [
    {
      role: 'assistant',
      text: 'Ask about the current client library or selected files.'
    }
  ];

  question = '';
  queryMode: QueryMode = 'hybrid';
  searchScope: 'all' | 'selected' = 'all';
  topK = 5;
  minSimilarity: number | null = null;
  semanticWeight = 0.65;
  keywordWeight = 0.35;
  useQueryRewrite = true;
  useQueryPlanner = true;
  isSending = false;
  statusMessage = '';
  statusType: 'idle' | 'error' = 'idle';

  constructor(private readonly queryEngine: QueryEngineService) {}

  get canUseSelectedScope(): boolean {
    return this.selectedFiles.length > 0;
  }

  send(): void {
    const trimmed = this.question.trim();
    if (!trimmed) return;
    const history = this.buildChatHistory();

    const scopedFileIds = this.searchScope === 'selected'
      ? this.selectedFiles.map((file) => file.fileId)
      : [];

    if (this.searchScope === 'selected' && scopedFileIds.length === 0) {
      this.setStatus('Select at least one file or switch scope to all files.', 'error');
      return;
    }

    this.messages = [...this.messages, { role: 'user', text: trimmed }];
    this.question = '';
    this.isSending = true;
    this.setStatus('Searching...', 'idle');

    this.queryEngine.ask(this.queryMode, this.buildRequest(trimmed, history), scopedFileIds).subscribe({
      next: (responses) => {
        this.isSending = false;
        this.setStatus('', 'idle');
        this.messages = [
          ...this.messages,
          {
            role: 'assistant',
            text: this.combineAnswerText(responses),
            renderedAnswer: this.renderAnswer(responses),
            responses
          }
        ];
      },
      error: (error: Error) => {
        this.isSending = false;
        this.setStatus(error.message || 'Query failed.', 'error');
      }
    });
  }

  clearSession(): void {
    this.messages = [
      {
        role: 'assistant',
        text: 'Ask about the current client library or selected files.'
      }
    ];
    this.statusMessage = '';
  }

  private buildRequest(question: string, history: ChatHistoryMessage[]): QueryRequest | HybridQueryRequest {
    const base: QueryRequest = {
      question,
      history,
      top_k: this.topK,
      client_id: this.clientId || undefined,
      min_similarity: this.minSimilarity ?? undefined,
      use_query_planner: this.useQueryPlanner,
      use_query_rewrite: this.useQueryRewrite,
      max_rewrites: this.useQueryRewrite ? 3 : 0
    };

    if (this.queryMode === 'semantic') return base;

    return {
      ...base,
      semantic_weight: this.semanticWeight,
      keyword_weight: this.keywordWeight
    };
  }

  private buildChatHistory(): ChatHistoryMessage[] {
    return this.messages
      .filter((message) => message.text.trim())
      .slice(-ChatPanelComponent.chatHistoryLimit)
      .map((message) => ({
        role: message.role,
        content: message.text
      }));
  }

  private combineAnswerText(responses: QueryResponse[]): string {
    if (responses.length === 1) return responses[0].answer;

    return responses
      .map((response) => {
        const filename = response.citations[0]?.filename || 'Selected file';
        return `${filename}\n${response.answer}`;
      })
      .join('\n\n');
  }

  private renderAnswer(responses: QueryResponse[]): string {
    return responses
      .map((response) => this.unwrapRagOutput(response.answer))
      .join('<hr />');
  }

  private unwrapRagOutput(answer: string): string {
    return answer
      .replace(/<\/?rag-output-list>/g, '')
      .replace(/<\/?rag-output-table>/g, '')
      .replace(/<rag-output-chart>/g, '<pre class="chart-spec">')
      .replace(/<\/rag-output-chart>/g, '</pre>');
  }

  private setStatus(message: string, type: 'idle' | 'error'): void {
    this.statusMessage = message;
    this.statusType = type;
  }
}
