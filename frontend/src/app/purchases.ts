import { DatePipe, DecimalPipe } from "@angular/common";
import { Component, computed, inject, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Language } from "./language";
import { ActivatedRoute, Router, RouterLink } from "@angular/router";
import { Modal } from "./modal";
import { Purchase, purchaseStatus, Supplier } from "./purchase-types";
import { Store } from "./store";

@Component({
  imports: [DatePipe, DecimalPipe, FormsModule, RouterLink, Modal],
  templateUrl: "./purchases.html",
})
export class Purchases {
  readonly message = inject(Language).message;
  readonly locale = inject(Language).locale;
  s = inject(Store);
  readonly t = inject(Language).translate;
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  rows = signal<Purchase[]>([]);
  suppliers = signal<Supplier[]>([]);
  supplierId = signal<number | null>(null);
  statusFilter = signal("all");
  selectedId = signal<number | null>(null);
  creating = signal(false);
  loading = signal(true);
  busy = signal(false);
  error = signal("");
  statusLabels = purchaseStatus;
  quantities = signal<Record<string, number>>({});
  selected = computed(() => this.rows().find(row => row.id === this.selectedId()));
  currentSupplier = computed(() => this.suppliers().find(row => row.id === this.supplierId()));
  activeSuppliers = computed(() => this.suppliers().filter(row => row.agreement_active));
  filtered = computed(() => this.rows().filter(row => this.statusFilter() === "all" || row.status === this.statusFilter()));
  orderLines = computed(() => Object.entries(this.quantities()).filter(([, qty]) => qty > 0)
    .map(([sku, qty]) => ({ sku, qty })));
  validOrder = computed(() => Object.values(this.quantities()).every(qty => qty >= 0) &&
    this.orderLines().length > 0 && this.orderLines().length <= 50 &&
    this.orderLines().every(line => Number.isSafeInteger(line.qty) && line.qty <= 100000 &&
      this.currentSupplier()?.offers.some(offer => offer.sku === line.sku &&
        (offer.available_qty === null || line.qty <= offer.available_qty))));

  constructor() {
    this.route.queryParamMap.subscribe(params => {
      const order = params.get("order");
      this.selectedId.set(order ? Number(order) : null);
      const supplier = params.get("supplier");
      if (supplier) this.openCreate(Number(supplier));
    });
    if (this.s.warehouse()) void this.load();
  }

  async load() {
    this.loading.set(true);
    this.error.set("");
    try {
      const [orders, suppliers] = await Promise.all([
        this.s.request<Purchase[]>("/purchases"),
        this.s.request<Supplier[]>("/suppliers"),
      ]);
      this.rows.set(orders);
      this.suppliers.set(suppliers);
      if (!this.supplierId()) this.supplierId.set(this.activeSuppliers()[0]?.id ?? null);
    } catch (error) {
      this.error.set((error as Error).message);
    } finally {
      this.loading.set(false);
    }
  }

  openCreate(supplierId = this.activeSuppliers()[0]?.id ?? null) {
    this.error.set("");
    this.supplierId.set(supplierId);
    this.quantities.set({});
    this.creating.set(true);
  }

  closeOverlay() {
    this.creating.set(false);
    this.selectedId.set(null);
    this.error.set("");
    if (this.route.snapshot.queryParamMap.keys.length) void this.router.navigate(["/purchases"]);
  }

  setQuantity(sku: string, qty: number | null) {
    this.quantities.update(rows => ({ ...rows, [sku]: qty || 0 }));
  }

  async create() {
    if (!this.currentSupplier()?.agreement_active || !this.validOrder() || this.busy()) return;
    this.busy.set(true);
    this.error.set("");
    try {
      const order = await this.s.request<Purchase>("/purchases", "POST", {
        supplier_id: this.supplierId(), lines: this.orderLines(),
      });
      this.rows.update(rows => [order, ...rows]);
      this.creating.set(false);
      this.selectedId.set(order.id);
      void this.router.navigate(["/purchases"], { queryParams: { order: order.id }, replaceUrl: true });
      this.s.notify("Purchase order placed");
    } catch (error) {
      this.error.set((error as Error).message);
    } finally {
      this.busy.set(false);
    }
  }

  async ship(order: Purchase) {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set("");
    try {
      await this.s.request("/purchases/" + order.id + "/ship", "POST");
      this.rows.update(rows => rows.map(row => row.id === order.id ? { ...row, status: "in_transit" } : row));
      this.s.notify("Purchase marked in transit");
    } catch (error) {
      this.error.set((error as Error).message);
    } finally {
      this.busy.set(false);
    }
  }
}
