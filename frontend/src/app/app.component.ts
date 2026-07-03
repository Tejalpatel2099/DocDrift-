import { Component, OnInit, OnDestroy, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { ApiService, HealthResponse, Repo, JobStatus } from './core/api.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule, FormsModule, MatButtonModule, MatCardModule, MatIconModule,
    MatProgressBarModule, MatProgressSpinnerModule, MatFormFieldModule, MatInputModule,
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent implements OnInit, OnDestroy {
  private api = inject(ApiService);
  private pollHandle: any = null;

  health = signal<HealthResponse | null>(null);
  repos = signal<Repo[]>([]);
  repoUrl = signal<string>('');
  submitting = signal<boolean>(false);
  errorMsg = signal<string>('');
  job = signal<JobStatus | null>(null);

  backendReady = computed(() => !!this.health()?.supabaseConfigured);
  percent = computed(() => {
    const j = this.job();
    if (!j) return 0;
    if (j.status === 'ready') return 100;
    if (j.phase === 'embedding') return 90;
    const total = j.total_files || 0;
    const done = j.processed_files || 0;
    return total ? Math.min(85, Math.round((done / total) * 85)) : 8;
  });

  ngOnInit(): void {
    this.api.getHealth().subscribe({ next: (h) => this.health.set(h) });
    this.loadRepos();
  }
  ngOnDestroy(): void { this.stopPolling(); }

  loadRepos(): void {
    this.api.listRepos().subscribe({
      next: (r) => this.repos.set(r),
      error: () => this.repos.set([]),
    });
  }

  index(): void {
    const url = this.repoUrl().trim();
    if (!url) return;
    this.submitting.set(true);
    this.errorMsg.set('');
    this.job.set({ status: 'indexing', phase: 'fetching' });
    this.api.createRepo(url).subscribe({
      next: (res) => {
        this.submitting.set(false);
        this.startPolling(res.repo_id);
        this.loadRepos();
      },
      error: (e) => {
        this.submitting.set(false);
        this.job.set(null);
        this.errorMsg.set(
          e?.status === 503
            ? 'Backend has no Supabase connection yet. Add credentials to backend/.env.'
            : e?.error?.detail || e?.message || 'Failed to start indexing.',
        );
      },
    });
  }

  private startPolling(repoId: string): void {
    this.stopPolling();
    this.pollHandle = setInterval(() => {
      this.api.repoStatus(repoId).subscribe({
        next: (s) => {
          this.job.set(s);
          if (s.status === 'ready' || s.status === 'error') {
            this.stopPolling();
            this.loadRepos();
          }
        },
      });
    }, 2000);
  }
  private stopPolling(): void {
    if (this.pollHandle) { clearInterval(this.pollHandle); this.pollHandle = null; }
  }
}
