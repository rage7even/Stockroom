import { Component, inject, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Language } from "./language";
import { Store } from "./store";

type SecurityAction = "recovery_email" | "password";

interface SecurityState {
  recovery_email: string | null;
  can_link_email: boolean;
  requires_setup_key: boolean;
}

@Component({
  selector: "sr-profile-security",
  imports: [FormsModule],
  styles: [":host { display: block; margin-top: 16px; }"],
  templateUrl: "./profile-security.html",
})
export class ProfileSecurity {
  private readonly store = inject(Store);
  private readonly language = inject(Language);
  readonly t = this.language.translate;
  readonly errorMessage = this.language.message;
  readonly state = signal<SecurityState | null>(null);
  readonly busy = signal(false);
  readonly error = signal("");
  readonly notice = signal("");
  readonly action = signal<SecurityAction | null>(null);
  readonly challenge = signal<{ requires_old_code: boolean } | null>(null);

  currentPassword = "";
  email = "";
  setupKey = "";
  code = "";
  oldCode = "";
  password = "";
  confirmation = "";

  constructor() {
    void this.load();
  }

  async load() {
    await this.run(async () => {
      this.state.set(await this.store.request<SecurityState>("/auth/profile-security"));
    });
  }

  choose(action: SecurityAction | null) {
    this.clearFields();
    this.action.set(action);
    this.error.set("");
    this.notice.set("");
  }

  async requestCode() {
    const action = this.action();
    if (!action) return;
    await this.run(async () => {
      const result = await this.store.request<{ requires_old_code: boolean }>("/auth/profile-security/request", "POST", {
        action,
        current_password: this.currentPassword,
        ...(action === "recovery_email" ? { email: this.email } : {}),
        ...(action === "recovery_email" && this.state()?.requires_setup_key ? { setup_key: this.setupKey } : {}),
      });
      this.currentPassword = "";
      this.setupKey = "";
      this.challenge.set(result);
    });
  }

  async confirm() {
    const action = this.action();
    const challenge = this.challenge();
    if (!action || !challenge) return;
    if (action === "password" && this.password !== this.confirmation) {
      this.error.set("Passwords do not match.");
      return;
    }
    await this.run(async () => {
      const state = await this.store.request<SecurityState>("/auth/profile-security/confirm", "POST", {
        action,
        code: this.code,
        ...(challenge.requires_old_code ? { old_code: this.oldCode } : {}),
        ...(action === "password" ? { password: this.password } : {}),
      });
      this.state.set(state);
      this.choose(null);
      this.notice.set(action === "password" ? "Password updated." : "Recovery email verified and linked.");
    });
  }

  private clearFields() {
    this.challenge.set(null);
    this.currentPassword = "";
    this.setupKey = "";
    this.email = "";
    this.code = "";
    this.oldCode = "";
    this.password = "";
    this.confirmation = "";
  }

  private async run(operation: () => Promise<void>) {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set("");
    try {
      await operation();
    } catch (error) {
      this.error.set((error as Error).message);
    } finally {
      this.busy.set(false);
    }
  }
}
