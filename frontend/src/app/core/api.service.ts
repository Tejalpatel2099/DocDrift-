import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface HelloResponse {
  service: string;
  message: string;
  time: string;
}

export interface HealthResponse {
  status: string;
  supabaseConfigured: boolean;
  database: { ok: boolean; detail: string };
}

/**
 * Single place that knows how to talk to the DocDrift API. Components inject
 * this instead of using HttpClient directly, so the base URL and endpoint
 * shapes live in one file.
 */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private base = environment.apiBaseUrl;

  getHello(): Observable<HelloResponse> {
    return this.http.get<HelloResponse>(`${this.base}/api/hello`);
  }

  getHealth(): Observable<HealthResponse> {
    return this.http.get<HealthResponse>(`${this.base}/api/health`);
  }
}
