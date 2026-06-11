import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { UploadMetadata } from '../../models/document.models';
import { DocumentUploadService } from '../../services/document-upload.service';

@Component({
  selector: 'app-upload-document',
  imports: [CommonModule, FormsModule],
  templateUrl: './upload-document.component.html',
  styleUrl: './upload-document.component.scss'
})
export class UploadDocumentComponent {
  readonly fixedUserId = 'USER0001';
  readonly acceptedMimeTypes = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'image/jpeg',
    'image/png',
    'image/tiff',
    'image/webp',
    'text/plain',
    'text/csv'
  ].join(',');

  selectedFile: File | null = null;
  isUploading = false;
  statusMessage = '';
  statusType: 'idle' | 'success' | 'error' = 'idle';

  metadata: UploadMetadata = {
    clientId: 'client_acme_001',
    userId: this.fixedUserId,
    fileType: 'contract',
    fileSubType: '',
    docType: 'unstructured',
    stage: 'review',
    parentFolder: '',
    uploadedBy: '',
    description: '',
    linked: false,
    tags: [
      { key: 'searchable', value: 'true' },
      { key: '', value: '' }
    ]
  };

  constructor(private readonly uploadService: DocumentUploadService) {}

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.selectedFile = input.files?.[0] ?? null;
    this.statusMessage = this.selectedFile
      ? `${this.selectedFile.name} selected`
      : '';
    this.statusType = 'idle';
  }

  addTag(): void {
    this.metadata.tags = [...this.metadata.tags, { key: '', value: '' }];
  }

  addPresetTag(key: string, value: string): void {
    this.metadata.tags = [{ key, value }, ...this.metadata.tags];
  }

  removeTag(index: number): void {
    this.metadata.tags = this.metadata.tags.filter((_, tagIndex) => tagIndex !== index);
  }

  upload(): void {
    if (!this.selectedFile || !this.metadata.clientId || !this.metadata.fileType) {
      this.setStatus('Select a file and enter clientId plus file type.', 'error');
      return;
    }

    this.isUploading = true;
    this.setStatus('Registering document metadata...', 'idle');

    this.uploadService.uploadDocument(this.selectedFile, {
      ...this.metadata,
      userId: this.fixedUserId
    }).subscribe({
      next: (result) => {
        this.isUploading = false;
        this.setStatus(`Uploaded ${result.metadata.fileName || this.selectedFile?.name} as ${result.fileId}`, 'success');
        this.selectedFile = null;
      },
      error: (error: Error) => {
        this.isUploading = false;
        this.setStatus(error.message || 'Upload failed.', 'error');
      }
    });
  }

  private setStatus(message: string, type: 'idle' | 'success' | 'error'): void {
    this.statusMessage = message;
    this.statusType = type;
  }
}
