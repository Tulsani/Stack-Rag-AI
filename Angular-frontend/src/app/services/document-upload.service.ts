import { Injectable } from '@angular/core';
import { HttpClient, HttpContext, HttpHeaders } from '@angular/common/http';
import { map, Observable, switchMap, throwError } from 'rxjs';

import { UploadInitResponse, UploadMetadata, UploadResult } from '../models/document.models';
import { SKIP_API_KEY } from './api-key.interceptor';

@Injectable({
  providedIn: 'root'
})
export class DocumentUploadService {
  private readonly uploaderUrl: string = 'http://sai-query-alb-176439024.us-east-1.elb.amazonaws.com/ingestion/upload';

  constructor(private readonly http: HttpClient) {}

  uploadDocument(file: File, metadata: UploadMetadata): Observable<UploadResult> {
    if (!this.uploaderUrl) {
      return throwError(() => new Error('Document uploader service URL is empty.'));
    }

    const headers = this.buildHeaders(file, metadata);

    return this.http.post<UploadInitResponse>(this.uploaderUrl, null, { headers }).pipe(
      switchMap((response) =>
        this.http.put(response.uploadUrl, file, {
          context: new HttpContext().set(SKIP_API_KEY, true),
          headers: new HttpHeaders({ 'Content-Type': file.type }),
          responseType: 'text'
        }).pipe(
          map(() => (
            {
              fileId: response.fileId,
              s3Key: response.s3Key,
              metadata: response.metadata
            }
          ))
        )
      )
    );
  }

  private buildHeaders(file: File, metadata: UploadMetadata): HttpHeaders {
    const headers: Record<string, string> = {
      'Content-Type': file.type,
      'x-doc-filename': file.name,
      'x-doc-file-size': String(file.size),
      'x-doc-client-id': metadata.clientId,
      'x-doc-user-id': metadata.userId,
      'x-doc-file-type': metadata.fileType,
      'x-doc-linked': String(metadata.linked),
      'x-doc-tags': JSON.stringify(metadata.tags.filter((tag) => tag.key && tag.value))
    };

    this.setOptionalHeader(headers, 'x-doc-file-sub-type', metadata.fileSubType);
    this.setOptionalHeader(headers, 'x-doc-doc-type', metadata.docType);
    this.setOptionalHeader(headers, 'x-doc-stage', metadata.stage);
    this.setOptionalHeader(headers, 'x-doc-parent-folder', metadata.parentFolder);
    this.setOptionalHeader(headers, 'x-doc-uploaded-by', metadata.uploadedBy);
    this.setOptionalHeader(headers, 'x-doc-description', metadata.description);

    return new HttpHeaders(headers);
  }

  private setOptionalHeader(headers: Record<string, string>, key: string, value?: string): void {
    const normalized = value?.trim();
    if (normalized) headers[key] = normalized;
  }
}
