import { Component, inject, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Store, User } from "./store";
import { Icon } from "./icon";
import { ThemeToggle } from "./theme-toggle";
import { Language, LanguageSelect } from "./language";

@Component({
  selector: "sr-auth",
  imports: [FormsModule, Icon, ThemeToggle, LanguageSelect],
  templateUrl: "./auth.html",
})
export class Auth {
  readonly label = inject(Language).label;
  readonly message = inject(Language).message;
  readonly s = inject(Store);
  readonly t = inject(Language).translate;
  readonly showPassword = signal(false);
  readonly busy = signal(false);
  readonly error = signal("");
  readonly notice = signal("");
  readonly mode = signal<"login" | "request" | "confirm">("login");
  readonly resendUntil = signal(0);
  login = "";
  password = "";
  email = "";
  code = "";
  newPassword = "";
  confirmation = "";

  demo(role: string) {
    this.login = role + "@stockroom.local";
    this.password = "Stockroom2026!";
  }

  setMode(mode: "login" | "request" | "confirm") {
    this.error.set("");
    this.notice.set("");
    this.code = "";
    this.newPassword = "";
    this.confirmation = "";
    this.password = "";
    this.showPassword.set(false);
    this.mode.set(mode);
  }

  async submit() {
    await this.run(async () => {
      this.s.user.set(await this.s.request<User>("/auth/login", "POST", {
        login: this.login, password: this.password,
      }));
      await this.s.refresh();
    });
  }

  async requestCode() {
    await this.run(async () => {
      await this.s.request("/auth/password-reset/request", "POST", { email: this.email });
      this.mode.set("confirm");
      this.code = "";
      this.notice.set("If that address is linked to an account, we’ll email a code.");
      const started = Date.now();
      this.resendUntil.set(started);
      setTimeout(() => {
        if (this.resendUntil() === started) this.resendUntil.set(0);
      }, 60_000);
    });
  }

  async resetPassword() {
    if (this.newPassword !== this.confirmation) {
      this.error.set("Passwords do not match.");
      return;
    }
    await this.run(async () => {
      await this.s.request("/auth/password-reset/confirm", "POST", {
        email: this.email, code: this.code, password: this.newPassword,
      });
      this.setMode("login");
      this.notice.set("Password changed. Sign in with your new password.");
    });
  }

  private async run(action: () => Promise<void>) {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set("");
    try {
      await action();
    } catch (error) {
      this.error.set((error as Error).message);
    } finally {
      this.busy.set(false);
    }
  }
}
