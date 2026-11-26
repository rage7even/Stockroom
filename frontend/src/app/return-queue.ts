import { Language } from "./language";
import { DatePipe } from "@angular/common";
import { Component, computed, inject, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { RouterLink } from "@angular/router";
import { Icon } from "./icon";
import { Store } from "./store";

type ReturnStatus = "pending" | "received" | "rejected";
interface ReturnRow {
  id: number;
  order_id: string;
  shop_name: string;
  product_name: string;
  sku: string;
  good: number;
  defective: number;
  reason: string;
  created_at: string;
  status: ReturnStatus;
}

@Component({
  standalone: true,
  imports: [DatePipe, FormsModule, RouterLink, Icon],
  templateUrl: "./return-queue.html",
})
export class ReturnQueue {
  readonly t = inject(Language).translate;
  readonly label = inject(Language).label;
  readonly message = inject(Language).message;
  readonly locale = inject(Language).locale;
  s = inject(Store);
  rows = signal<ReturnRow[]>([]);
  busy = signal(false);
  error = signal("");
  query = signal("");
  status = signal<ReturnStatus | "all">("pending");
  statuses = ["pending", "received", "rejected", "all"] as const;
  filtered = computed(() => {
    const status = this.status();
    const query = this.query().trim().toLowerCase();
    return this.rows().filter(row =>
      (status === "all" || row.status === status) &&
      `${row.order_id} ${row.shop_name} ${row.sku} ${row.product_name}`.toLowerCase().includes(query)
    );
  });

  constructor() {
    if (this.s.warehouse()) void this.load();
  }

  count(status: ReturnStatus | "all") {
    return this.rows().filter(row => status === "all" || row.status === status).length;
  }

  async load() {
    this.busy.set(true);
    this.error.set("");
    try {
      this.rows.set(await this.s.request<ReturnRow[]>("/returns"));
    } catch (error) {
      this.error.set((error as Error).message);
    } finally {
      this.busy.set(false);
    }
  }
}
