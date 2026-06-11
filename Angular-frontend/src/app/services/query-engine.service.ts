import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, forkJoin, map, throwError } from 'rxjs';

import { HybridQueryRequest, QueryMode, QueryRequest, QueryResponse } from '../models/document.models';

@Injectable({
  providedIn: 'root'
})
export class QueryEngineService {
  private readonly queryEngineUrl: string = 'http://sai-query-alb-176439024.us-east-1.elb.amazonaws.com';

  constructor(private readonly http: HttpClient) {}

  ask(
    mode: QueryMode,
    request: QueryRequest | HybridQueryRequest,
    fileIds: string[] = []
  ): Observable<QueryResponse[]> {
    if (!this.queryEngineUrl) {
      return throwError(() => new Error('Query engine service URL is empty.'));
    }

    const endpoint = mode === 'hybrid' ? 'query/hybrid' : 'query';
    const url = `${this.queryEngineUrl.replace(/\/$/, '')}/${endpoint}`;
    const scopedRequests = fileIds.length
      ? fileIds.map((fileId) => ({ ...request, file_id: fileId }))
      : [request];

    return forkJoin(scopedRequests.map((body) => this.http.post<QueryResponse>(url, body))).pipe(
      map((responses) => responses)
    );
  }
}
