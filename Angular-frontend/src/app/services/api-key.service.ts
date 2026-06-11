import { Injectable } from '@angular/core';

const API_KEY_STORAGE_KEY = 'sai-api-key';

@Injectable({
  providedIn: 'root'
})
export class ApiKeyService {
  getApiKey(): string {
    return localStorage.getItem(API_KEY_STORAGE_KEY) || '';
  }

  hasApiKey(): boolean {
    return Boolean(this.getApiKey());
  }

  saveApiKey(apiKey: string): void {
    const normalized = apiKey.trim();
    if (normalized) {
      localStorage.setItem(API_KEY_STORAGE_KEY, normalized);
    }
  }

  clearApiKey(): void {
    localStorage.removeItem(API_KEY_STORAGE_KEY);
  }
}
