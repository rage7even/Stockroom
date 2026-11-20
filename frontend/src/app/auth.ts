import { Component, inject, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Store, User } from "./store";
import { Icon } from "./icon";
import { ThemeToggle } from "./theme-toggle";
@Component({
  selector: "sr-auth",
  standalone: true,
  imports: [FormsModule, Icon, ThemeToggle],
  templateUrl: "./auth.html",
})
export class Auth {
  s = inject(Store);
  showPassword = signal(false);
  busy = signal(false);
  error = signal("");
  login = "";
  password = "";
  demo(role: string) {
    this.login = role + "@stockroom.local";
    this.password = "Stockroom2026!";
  }
  async submit() {
    this.busy.set(true);
    this.error.set("");
    try {
      this.s.user.set(
        await this.s.request<User>(
          "/auth/login",
          "POST",
          { login: this.login, password: this.password },
        ),
      );
      await this.s.refresh();
    } catch (e) {
      this.error.set((e as Error).message);
    } finally {
      this.busy.set(false);
    }
  }
}
