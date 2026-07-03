import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { AppComponent } from './app/app.component';
import { environment } from './environments/environment';

bootstrapApplication(AppComponent, appConfig).catch((err) => {
  // Only surface bootstrap failures in development; production stays quiet.
  if (!environment.production) {
    console.error(err);
  }
});
