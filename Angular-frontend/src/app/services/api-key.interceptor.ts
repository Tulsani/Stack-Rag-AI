import { HttpContextToken, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { throwError } from 'rxjs';

import { ApiKeyService } from './api-key.service';

export const SKIP_API_KEY = new HttpContextToken<boolean>(() => false);

export const apiKeyInterceptor: HttpInterceptorFn = (request, next) => {
  if (request.context.get(SKIP_API_KEY)) {
    return next(request);
  }

  const apiKey = inject(ApiKeyService).getApiKey();
  if (!apiKey) {
    return throwError(() => new Error('Enter the API key before using the app.'));
  }

  return next(
    request.clone({
      setHeaders: {
        'x-api-key-header': apiKey
      }
    })
  );
};
