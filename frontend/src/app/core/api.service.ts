import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface HelloResponse { service: string; message: string; time: string; }
export interface HealthResponse {
  status: string;
  supabaseConfigured: boolean;
  openaiConfigured: boolean;
  githubTokenSet: boolean;
  database: { ok: boolean; detail: string };
}
export interface Repo {
  id: string;
  github_url: string;
  name: string;
  default_branch?: string;
  status: string;
  last_indexed_at?: string;
  created_at?: string;
}
export interface JobStatus {
  status: string;          // pending | indexing | ready | error | not_found
  phase?: string;          // fetching | embedding | done
  processed_files?: number;
  total_files?: number;
  chunks?: number;
  error?: string | null;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private base = environment.apiBaseUrl;

  getHealth(): Observable<HealthResponse> {
    return this.http.get<HealthResponse>(`${this.base}/api/health`);
  }
  listRepos(): Observable<Repo[]> {
    return this.http.get<Repo[]>(`${this.base}/api/repos`);
  }
  createRepo(githubUrl: string): Observable<{ repo_id: string; status: string; name: string }> {
    return this.http.post<{ repo_id: string; status: string; name: string }>(
      `${this.base}/api/repos`, { github_url: githubUrl },
    );
  }
  repoStatus(repoId: string): Observable<JobStatus> {
    return this.http.get<JobStatus>(`${this.base}/api/repos/${repoId}/status`);
  }
}
