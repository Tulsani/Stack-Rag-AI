import { Routes } from '@angular/router';

import { DocLibraryComponent } from './pages/doc-library/doc-library.component';
import { UploadDocumentComponent } from './pages/upload-document/upload-document.component';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'library' },
  { path: 'library', component: DocLibraryComponent },
  { path: 'upload', component: UploadDocumentComponent },
  { path: '**', redirectTo: 'library' }
];
