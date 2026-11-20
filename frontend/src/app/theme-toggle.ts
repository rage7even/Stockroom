import { DOCUMENT } from "@angular/common";
import { Component, inject, signal } from "@angular/core";
import { Icon } from "./icon";

@Component({
  selector: "sr-theme-toggle",
  standalone: true,
  imports: [Icon],
  template: `
    <button
      type="button"
      class="icon-button theme-toggle"
      aria-label="Dark theme"
      [attr.aria-pressed]="dark()"
      [title]="dark() ? 'Switch to light theme' : 'Switch to dark theme'"
      (click)="toggle()"
    >
      <sr-icon [name]="dark() ? 'sun' : 'moon'" />
    </button>
  `,
})
export class ThemeToggle {
  private readonly root = inject(DOCUMENT).documentElement;
  readonly dark = signal(this.root.dataset["theme"] === "dark");

  toggle() {
    const theme = this.dark() ? "light" : "dark";
    this.root.dataset["theme"] = theme;
    this.dark.set(theme === "dark");
    try {
      localStorage.setItem("stockroom-theme", theme);
    } catch {
      // The current page still supports switching when browser storage is unavailable.
    }
  }
}
