import { DOCUMENT } from "@angular/common";
import { Component, inject, signal } from "@angular/core";
import { Icon } from "./icon";
import { Language } from "./language";

@Component({
  selector: "sr-theme-toggle",
  standalone: true,
  imports: [Icon],
  template: `
    <button
      type="button"
      class="icon-button theme-toggle"
      [attr.aria-label]="title()"
      [attr.aria-pressed]="dark()"
      [title]="title()"
      (click)="toggle()"
    >
      <sr-icon [name]="dark() ? 'sun' : 'moon'" />
    </button>
  `,
})
export class ThemeToggle {
  private readonly root = inject(DOCUMENT).documentElement;
  readonly dark = signal(this.root.dataset["theme"] === "dark");
  private readonly t = inject(Language).translate;
  title() { return this.t(this.dark() ? "Switch to light theme" : "Switch to dark theme"); }

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
