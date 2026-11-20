import { Component, inject, signal } from "@angular/core";
import { RouterLink } from "@angular/router";
import { Icon } from "./icon";
import { Store } from "./store";

interface RowError { row: number; message: string }
interface ImportSummary {
  created: number;
  updated: number;
  unchanged: number;
  applied: boolean;
}

@Component({
  standalone: true,
  imports: [RouterLink, Icon],
  templateUrl: "./catalogue-import.html",
})
export class CatalogueImport {
  s = inject(Store);
  file = signal<File | null>(null);
  summary = signal<ImportSummary | null>(null);
  rowErrors = signal<RowError[]>([]);
  error = signal("");
  busy = signal(false);

  pick(input: HTMLInputElement) {
    this.file.set(input.files?.[0] ?? null);
    this.summary.set(null);
    this.rowErrors.set([]);
    this.error.set("");
  }

  async run(operation: "preview" | "apply") {
    const file = this.file();
    if (!file || this.busy() || (operation === "apply" && (!this.summary() || this.summary()?.applied))) return;
    this.busy.set(true);
    this.error.set("");
    this.summary.set(null);
    this.rowErrors.set([]);
    const data = new FormData();
    data.append("file", file);
    data.append("operation", operation);
    try {
      this.summary.set(await this.s.request<ImportSummary>("/catalog-csv", "POST", data));
      if (operation === "apply") {
        this.s.notify("Catalogue imported");
        await this.s.refresh();
      }
    } catch (error) {
      const message = (error as Error).message;
      try {
        const details = JSON.parse(message);
        if (Array.isArray(details.errors)) {
          this.rowErrors.set(details.errors);
          return;
        }
      } catch {
        // Validation messages about the entire file are plain text.
      }
      this.error.set(message);
    } finally {
      this.busy.set(false);
    }
  }
}
