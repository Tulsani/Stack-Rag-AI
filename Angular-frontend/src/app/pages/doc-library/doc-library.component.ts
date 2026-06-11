import { CommonModule } from '@angular/common';
import { Component, HostListener, OnInit } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { FormsModule } from '@angular/forms';

import { ChatPanelComponent } from '../../components/chat-panel/chat-panel.component';
import { FileBrowserComponent } from '../../components/file-browser/file-browser.component';
import { DocumentFile, ListFolderResponse } from '../../models/document.models';
import { DocumentLibraryService } from '../../services/document-library.service';

@Component({
  selector: 'app-doc-library',
  imports: [CommonModule, FormsModule, FileBrowserComponent, ChatPanelComponent],
  templateUrl: './doc-library.component.html',
  styleUrl: './doc-library.component.scss'
})
export class DocLibraryComponent implements OnInit {
  clientId = 'client_acme_001';
  currentFolder = '';
  search = '';
  status = '';
  folderResponse: ListFolderResponse | null = null;
  selectedFiles: DocumentFile[] = [];
  selectedFileIds = new Set<string>();
  isLoading = false;
  statusMessage = '';
  statusType: 'idle' | 'error' = 'idle';
  isChatOpen = false;
  chatWidth = 460;
  isResizingChat = false;
  previewFile: DocumentFile | null = null;
  previewUrl = '';
  safePreviewUrl: SafeResourceUrl | null = null;
  isPreviewLoading = false;

  constructor(
    private readonly libraryService: DocumentLibraryService,
    private readonly sanitizer: DomSanitizer
  ) {}

  ngOnInit(): void {
    this.loadFolder();
  }

  loadFolder(folder = this.currentFolder): void {
    if (!this.clientId.trim()) {
      this.setStatus('Enter a clientId.', 'error');
      return;
    }

    this.currentFolder = folder;
    this.isLoading = true;
    this.setStatus('', 'idle');

    this.libraryService.listFolder({
      clientId: this.clientId.trim(),
      folder: this.currentFolder,
      search: this.search.trim(),
      status: this.status.trim()
    }).subscribe({
      next: (response) => {
        this.folderResponse = response;
        this.isLoading = false;
        this.pruneSelection(response.files);
      },
      error: (error: Error) => {
        this.isLoading = false;
        this.setStatus(error.message || 'Could not load document library.', 'error');
      }
    });
  }

  openFile(file: DocumentFile): void {
    this.isPreviewLoading = true;
    this.previewFile = file;
    this.previewUrl = '';
    this.safePreviewUrl = null;

    this.libraryService.getFile(file.fileId, this.clientId.trim()).subscribe({
      next: (response) => {
        this.isPreviewLoading = false;
        this.previewFile = response.file;
        this.previewUrl = response.viewUrl;
        this.safePreviewUrl = this.sanitizer.bypassSecurityTrustResourceUrl(response.viewUrl);
      },
      error: (error: Error) => {
        this.isPreviewLoading = false;
        this.closePreview();
        this.setStatus(error.message || 'Could not open file.', 'error');
      }
    });
  }

  closePreview(): void {
    this.previewFile = null;
    this.previewUrl = '';
    this.safePreviewUrl = null;
    this.isPreviewLoading = false;
  }

  openPreviewInNewTab(): void {
    if (!this.previewUrl) return;
    window.open(this.previewUrl, '_blank', 'noopener,noreferrer');
  }

  updateSelectedFiles(files: DocumentFile[]): void {
    this.selectedFiles = files;
    this.selectedFileIds = new Set(files.map((file) => file.fileId));
  }

  openChat(): void {
    this.isChatOpen = true;
  }

  closeChat(): void {
    this.isChatOpen = false;
    this.isResizingChat = false;
  }

  startChatResize(event: MouseEvent): void {
    event.preventDefault();
    this.isResizingChat = true;
  }

  @HostListener('document:mousemove', ['$event'])
  resizeChat(event: MouseEvent): void {
    if (!this.isResizingChat) return;

    const minWidth = 360;
    const maxWidth = Math.min(760, window.innerWidth - 420);
    const nextWidth = window.innerWidth - event.clientX;
    this.chatWidth = Math.max(minWidth, Math.min(maxWidth, nextWidth));
  }

  @HostListener('document:mouseup')
  stopChatResize(): void {
    this.isResizingChat = false;
  }

  clearFilters(): void {
    this.search = '';
    this.status = '';
    this.currentFolder = '';
    this.loadFolder('');
  }

  private pruneSelection(currentFiles: DocumentFile[]): void {
    const currentIds = new Set(currentFiles.map((file) => file.fileId));
    this.selectedFiles = this.selectedFiles.filter((file) => currentIds.has(file.fileId));
    this.selectedFileIds = new Set(this.selectedFiles.map((file) => file.fileId));
  }

  private setStatus(message: string, type: 'idle' | 'error'): void {
    this.statusMessage = message;
    this.statusType = type;
  }
}
