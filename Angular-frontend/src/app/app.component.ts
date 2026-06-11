import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { ApiKeyService } from './services/api-key.service';

@Component({
  selector: 'app-root',
  imports: [CommonModule, FormsModule, RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent {
  readonly appName = 'SAI Document Workbench';
  apiKeyInput = '';
  apiKeyError = '';

  constructor(private readonly apiKeyService: ApiKeyService) {}

  get hasApiKey(): boolean {
    return this.apiKeyService.hasApiKey();
  }

  saveApiKey(): void {
    if (!this.apiKeyInput.trim()) {
      this.apiKeyError = 'API key is required.';
      return;
    }

    this.apiKeyService.saveApiKey(this.apiKeyInput);
    this.apiKeyInput = '';
    this.apiKeyError = '';
  }

  changeApiKey(): void {
    this.apiKeyService.clearApiKey();
    this.apiKeyInput = '';
  }
}
