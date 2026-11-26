import { Language } from "./language";
import { DatePipe } from "@angular/common";
import { Component, computed, inject, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { ActivatedRoute, Router, RouterLink } from "@angular/router";
import { BarcodeScan } from "./barcode-scan";
import { Purchase, purchaseStatus, Receipt } from "./purchase-types";
import { newRequestId } from "./request-id";
import { Store } from "./store";

@Component({
  imports: [DatePipe, FormsModule, RouterLink, BarcodeScan],
  templateUrl: "./purchase-receiving.html",
})
export class PurchaseReceiving {
  readonly t = inject(Language).translate;
  readonly message = inject(Language).message;
  readonly locale = inject(Language).locale;
  s = inject(Store);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  rows = signal<Purchase[]>([]);
  selectedId = signal<number | null>(null);
  selected = computed(() => this.rows().find(row => row.id === this.selectedId()));
  quantities = signal<Record<string, number>>({});
  scanning = signal(false);
  lastScanned = signal("");
  saving = signal(false);
  loading = signal(true);
  error = signal("");
  statusLabels = purchaseStatus;
  submission = { orderId: 0, signature: "", id: "" };
  valid = computed(() => {
    const order = this.selected();
    if (!order || order.status === "received") return false;
    return order.lines.every(line => {
      const qty = this.quantities()[line.sku] ?? 0;
      return Number.isSafeInteger(qty) && qty >= 0 && qty <= line.remaining;
    }) && this.total() > 0;
  });
  total = computed(() => Object.values(this.quantities()).reduce((total, qty) => total + qty, 0));

  constructor() {
    this.route.queryParamMap.subscribe(params => {
      const order = params.get("order");
      this.selectedId.set(order ? Number(order) : null);
      this.quantities.set({});
      this.lastScanned.set("");
      this.error.set("");
    });
    if (this.s.warehouse()) void this.load();
  }

  async load() {
    this.loading.set(true);
    this.error.set("");
    try {
      this.rows.set(await this.s.request<Purchase[]>("/purchases"));
    } catch (error) {
      this.error.set((error as Error).message);
    } finally {
      this.loading.set(false);
    }
  }

  choose(id: number | null) {
    void this.router.navigate(["/purchase-receiving"], { queryParams: id ? { order: id } : {} });
  }

  setQuantity(sku: string, value: number | null) {
    this.quantities.update(rows => ({ ...rows, [sku]: value || 0 }));
  }

  async scan(code: string) {
    const orderId = this.selectedId();
    if (this.scanning() || this.saving()) return;
    this.scanning.set(true);
    this.error.set("");
    try {
      const product = await this.s.findBarcode(code);
      if (this.selectedId() !== orderId) return;
      const line = this.selected()?.lines.find(item => item.sku === product.sku);
      if (!line) throw new Error(product.product_name + " is not in this purchase order.");
      const count = (this.quantities()[line.sku] ?? 0) + 1;
      if (count > line.remaining) throw new Error("All expected units of " + product.product_name + " have been counted.");
      this.setQuantity(line.sku, count);
      this.lastScanned.set(line.sku);
    } catch (error) {
      this.error.set((error as Error).message);
    } finally {
      this.scanning.set(false);
    }
  }

  async confirm(order: Purchase) {
    if (this.saving() || this.scanning() || !this.valid()) return;
    const lines = order.lines.map(line => ({ sku: line.sku, qty: this.quantities()[line.sku] || 0 }))
      .filter(line => line.qty > 0);
    const signature = JSON.stringify(lines);
    if (this.submission.orderId !== order.id || this.submission.signature !== signature) {
      this.submission = { orderId: order.id, signature, id: newRequestId() };
    }
    this.saving.set(true);
    this.error.set("");
    try {
      const receipt = await this.s.request<Receipt>("/purchases/" + order.id + "/receipts", "POST", {
        receipt_id: this.submission.id, lines,
      });
      this.quantities.set({});
      this.lastScanned.set("");
      this.s.notify("Delivery receipt confirmed");
      if (!order.receipts.some(row => row.id === receipt.id)) {
        const updated = order.lines.map(line => {
          const count = receipt.lines.find(row => row.sku === line.sku)?.qty ?? 0;
          return { ...line, received: line.received + count, remaining: line.remaining - count };
        });
        this.rows.update(rows => rows.map(row => row.id === order.id ? {
          ...row, lines: updated, receipts: [...row.receipts, receipt],
          status: updated.some(line => line.remaining) ? "partial" : "received",
        } : row));
      }
      this.submission = { orderId: 0, signature: "", id: "" };
      await Promise.all([this.load(), this.s.refresh()]);
    } catch (error) {
      this.error.set((error as Error).message);
    } finally {
      this.saving.set(false);
    }
  }
}
