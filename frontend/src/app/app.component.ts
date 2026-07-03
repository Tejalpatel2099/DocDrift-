import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatChipsModule } from '@angular/material/chips';
import { ApiService, HelloResponse, HealthResponse } from './core/api.service';

type LoadState = 'loading' | 'ok' | 'error';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatCardModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatChipsModule,
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent implements OnInit {
  private api = inject(ApiService);

  state = signal<LoadState>('loading');
  hello = signal<HelloResponse | null>(null);
  health = signal<HealthResponse | null>(null);
  errorMsg = signal<string>('');

  ngOnInit(): void {
    this.check();
  }

  check(): void {
    this.state.set('loading');
    this.errorMsg.set('');
    this.api.getHello().subscribe({
      next: (h) => {
        this.hello.set(h);
        this.api.getHealth().subscribe({
          next: (hp) => {
            this.health.set(hp);
            this.state.set('ok');
          },
          error: (e) => this.fail(e),
        });
      },
      error: (e) => this.fail(e),
    });
  }

  private fail(e: unknown): void {
    this.state.set('error');
    const err = e as { message?: string; status?: number };
    this.errorMsg.set(
      err?.status === 0
        ? 'Cannot reach the API. Is the backend running on :8001?'
        : err?.message || 'Unknown error',
    );
  }
}
