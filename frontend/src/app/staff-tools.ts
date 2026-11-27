import { Language } from "./language";
import { Component, inject, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { DatePipe } from "@angular/common";
import { Store, User } from "./store";
import { ProfileSecurity } from "./profile-security";

@Component({
  imports: [FormsModule, ProfileSecurity],
  template: `
    <div class="page-heading"><div><h1>{{t('Profile')}}</h1><p>{{s.user()?.login}} · {{label(s.user()?.role)}}</p></div></div>
    <section class="panel">
      <form class="modal-form toolbar" (ngSubmit)="save()" #form="ngForm">
        @if (preview() || (s.user()?.avatar && !removePhoto)) {
          <img class="profile-photo" [src]="preview() || s.user()?.avatar" [alt]="t('Profile photo')" />
          <button class="btn" type="button" (click)="clearPhoto(photo)">{{t('Remove photo')}}</button>
        }
        <label>{{t('Photo')}}<input #photo type="file" accept="image/jpeg,image/png,image/webp"
          [disabled]="saving()" (change)="choosePhoto(photo)" /></label>
        <label>{{t('Full name')}}<input name="name" [(ngModel)]="name" required maxlength="80" /></label>
        <label>{{t('Phone')}}<input name="phone" type="tel" [(ngModel)]="phone" maxlength="25" /></label>
        <label>{{t('Job title')}}<input name="jobTitle" [(ngModel)]="jobTitle" maxlength="80" /></label>
        <button class="btn primary" [disabled]="!form.valid || saving()">{{t('Save profile')}}</button>
      </form>
    </section>
    <sr-profile-security />
  `,
})
export class Profile {
  readonly t = inject(Language).translate;
  readonly label = inject(Language).label;
  s = inject(Store);
  name = this.s.user()?.full_name ?? "";
  phone = this.s.user()?.phone ?? "";
  jobTitle = this.s.user()?.job_title ?? "";
  saving = signal(false);
  preview = signal("");
  photo?: File;
  removePhoto = false;

  choosePhoto(input: HTMLInputElement) {
    const file = input.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      this.s.error.set("Choose a photo up to 2 MB.");
      input.value = "";
      return;
    }
    this.photo = file;
    this.removePhoto = false;
    this.setPreview(URL.createObjectURL(file));
  }

  clearPhoto(input: HTMLInputElement) {
    this.photo = undefined;
    this.removePhoto = true;
    this.setPreview("");
    input.value = "";
  }

  ngOnDestroy() {
    this.setPreview("");
  }

  private setPreview(url: string) {
    if (this.preview()) URL.revokeObjectURL(this.preview());
    this.preview.set(url);
  }

  async save() {
    this.saving.set(true);
    this.s.error.set("");
    try {
      const fields = new FormData();
      fields.set("full_name", this.name);
      fields.set("phone", this.phone);
      fields.set("job_title", this.jobTitle);
      if (this.photo) fields.set("photo", this.photo);
      if (this.removePhoto) fields.set("remove_photo", "true");
      this.s.user.set(await this.s.request<User>("/auth/me", "PATCH", fields));
      this.name = this.s.user()?.full_name ?? "";
      this.setPreview("");
      this.photo = undefined;
      this.removePhoto = false;
      this.s.notify("Profile saved");
    } catch (error) {
      this.s.error.set((error as Error).message);
    } finally {
      this.saving.set(false);
    }
  }
}

interface Issue {
  id: number;
  title: string;
  description: string;
  status: string;
  author: string;
  created_at: string;
  attachment_url: string | null;
}

@Component({
  imports: [FormsModule, DatePipe],
  template: `
    <div class="page-heading"><div><h1>{{t('Report issue')}}</h1></div></div>
    <section class="panel">
      <form class="modal-form toolbar" (ngSubmit)="submit(attachment)" #form="ngForm">
        <label>{{t('Title')}}<input name="title" [(ngModel)]="title" maxlength="120" required /></label>
        <label>{{t('Description')}}<textarea name="description" [(ngModel)]="description" rows="3"
          maxlength="2000" [placeholder]="t('Page, steps, expected and actual result')" required></textarea></label>
        <label>{{t('Photo or screenshot (optional)')}}
          <input #attachment type="file" accept="image/jpeg,image/png,image/webp"
            [disabled]="saving()" (change)="attachmentError.set('')" />
          <small>{{t('JPEG, PNG or WebP · up to 5 MB')}}</small>
          @if (attachmentError()) { <small role="alert">{{message(attachmentError())}}</small> }
        </label>
        <button class="btn primary" [disabled]="!form.valid || saving()">{{t('Send issue')}}</button>
      </form>
    </section>
    <section class="panel">
      <div class="toolbar"><h2>{{t(canManage() ? "Issue queue" : "My issues")}}</h2></div>
      @for (issue of items(); track issue.id) {
        <div class="toolbar">
          <div>
            <strong>#{{issue.id}} · {{issue.title}}</strong>
            <p>{{issue.description}}</p>
            <small>{{issue.author}} · {{issue.created_at  | date:"short":undefined:locale()}}</small>
            @if (issue.attachment_url; as attachmentUrl) {
              <p><a class="btn small" [href]="attachmentUrl" target="_blank"
                rel="noopener noreferrer">{{t('Open attachment')}}</a></p>
            }
          </div>
          @if (canManage()) {
            <select [attr.aria-label]="t('Status for issue {0}', issue.id)" [ngModel]="issue.status"
              [disabled]="saving()" (ngModelChange)="changeStatus(issue, $event)">
              <option value="open">{{t('Open')}}</option>
              <option value="in_progress">{{t('In progress')}}</option>
              <option value="resolved">{{t('Resolved')}}</option>
            </select>
          } @else {
            <span class="badge blue">{{label(issue.status)}}</span>
          }
        </div>
      } @empty {
        <div class="toolbar">{{t('No issues yet.')}}</div>
      }
    </section>
  `,
})
export class Issues {
  readonly t = inject(Language).translate;
  readonly label = inject(Language).label;
  readonly message = inject(Language).message;
  readonly locale = inject(Language).locale;
  s = inject(Store);
  items = signal<Issue[]>([]);
  canManage = signal(false);
  saving = signal(false);
  title = "";
  description = "";
  attachmentError = signal("");

  constructor() {
    void this.load();
  }

  private async load() {
    try {
      const response = await this.s.request<{items: Issue[]; can_manage: boolean}>("/issues");
      this.items.set(response.items);
      this.canManage.set(response.can_manage);
    } catch (error) {
      this.s.error.set((error as Error).message);
    }
  }

  async submit(input: HTMLInputElement) {
    const file = input.files?.[0];
    if (file && file.size > 5 * 1024 * 1024) {
      this.attachmentError.set("Choose an image up to 5 MB.");
      return;
    }
    this.saving.set(true);
    this.s.error.set("");
    try {
      const fields = new FormData();
      fields.set("title", this.title);
      fields.set("description", this.description);
      if (file) fields.set("attachment", file);
      const issue = await this.s.request<Issue>("/issues", "POST", fields);
      this.title = "";
      this.description = "";
      input.value = "";
      this.items.update(items => [issue, ...items]);
      this.s.notify("Issue submitted");
    } catch (error) {
      this.s.error.set((error as Error).message);
    } finally {
      this.saving.set(false);
    }
  }

  async changeStatus(issue: Issue, status: string) {
    this.saving.set(true);
    this.s.error.set("");
    try {
      const updated = await this.s.request<Issue>("/issues/" + issue.id, "PATCH", { status });
      this.items.update(items => items.map(row => row.id === updated.id ? updated : row));
    } catch (error) {
      this.s.error.set((error as Error).message);
      await this.load();
    } finally {
      this.saving.set(false);
    }
  }
}
