import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';

import { DocumentFile, ListFolderResponse } from '../../models/document.models';

@Component({
  selector: 'app-file-browser',
  imports: [CommonModule],
  templateUrl: './file-browser.component.html',
  styleUrl: './file-browser.component.scss'
})
export class FileBrowserComponent {
  @Input() folderResponse: ListFolderResponse | null = null;
  @Input() selectedFileIds = new Set<string>();
  @Input() isLoading = false;

  @Output() folderChanged = new EventEmitter<string>();
  @Output() fileOpened = new EventEmitter<DocumentFile>();
  @Output() selectionChanged = new EventEmitter<DocumentFile[]>();

  get files(): DocumentFile[] {
    return this.folderResponse?.files ?? [];
  }

  get allCurrentFilesSelected(): boolean {
    return this.files.length > 0 && this.files.every((file) => this.selectedFileIds.has(file.fileId));
  }

  toggleFile(file: DocumentFile, checked: boolean): void {
    const next = new Set(this.selectedFileIds);
    checked ? next.add(file.fileId) : next.delete(file.fileId);
    this.emitSelection(next);
  }

  toggleCurrentFiles(checked: boolean): void {
    const next = new Set(this.selectedFileIds);
    for (const file of this.files) {
      checked ? next.add(file.fileId) : next.delete(file.fileId);
    }
    this.emitSelection(next);
  }

  formatDate(value: string): string {
    const numeric = Number(value);
    const date = Number.isFinite(numeric) && numeric > 0 ? new Date(numeric) : new Date(value);
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString();
  }

  private emitSelection(nextIds: Set<string>): void {
    const selected = this.files.filter((file) => nextIds.has(file.fileId));
    this.selectionChanged.emit(selected);
  }
}
