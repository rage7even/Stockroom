import { Component, inject, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Store, User } from "./store";
import { Icon } from "./icon";
@Component({
  selector: "sr-auth",
  standalone: true,
  imports: [FormsModule, Icon],
  templateUrl: "./auth.html",
})
export class Auth {
  s = inject(Store);
  register = signal(false);
  showPassword = signal(false);
  busy = signal(false);
  error = signal("");
  login = "";
  password = "";
  name = "";
  demo(role: string) {
    this.login = role + "@stockroom.local";
    this.password = "Stockroom2026!";
    this.register.set(false);
  }
  async submit() {
    this.busy.set(true);
    this.error.set("");
    try {
      const body = this.register()
        ? { login: this.login, password: this.password, full_name: this.name }
        : { login: this.login, password: this.password };
      this.s.user.set(
        await this.s.request<User>(
          "/auth/" + (this.register() ? "register" : "login"),
          "POST",
          body,
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
