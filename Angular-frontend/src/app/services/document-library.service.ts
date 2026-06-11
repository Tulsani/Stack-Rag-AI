import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';

import { FileViewResponse, ListFolderResponse } from '../models/document.models';

@Injectable({
  providedIn: 'root'
})
export class DocumentLibraryService {
  private readonly libraryUrl: string = 'https://szsvtbz3m9.execute-api.us-east-1.amazonaws.com/default/KRS-docLibrary';

  constructor(private readonly http: HttpClient) {}

  listFolder(params: {
    clientId: string;
    folder?: string;
    search?: string;
    status?: string;
  }): Observable<ListFolderResponse> {
    if (!this.libraryUrl) {
      return throwError(() => new Error('Document library service URL is empty.'));
    }

    return this.http.post<ListFolderResponse>(this.libraryUrl, {
      requestType: 'list-folder',
      clientId: params.clientId,
      folder: params.folder ?? '',
      search: params.search ?? '',
      status: params.status ?? ''
    });
  }

  getFile(fileId: string, clientId: string): Observable<FileViewResponse> {
    if (!this.libraryUrl) {
      return throwError(() => new Error('Document library service URL is empty.'));
    }

    return this.http.post<FileViewResponse>(this.libraryUrl, {
      requestType: 'get-file',
      fileId,
      clientId
    });
  }
}
