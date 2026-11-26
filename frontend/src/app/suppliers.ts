import { Language } from "./language";
import { DatePipe, DecimalPipe } from "@angular/common";
import { Component, computed, inject, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { RouterLink } from "@angular/router";
import { Modal } from "./modal";
import { Offer, Supplier, SupplierForm } from "./purchase-types";
import { Store } from "./store";

@Component({
  imports: [DatePipe, DecimalPipe, FormsModule, RouterLink, Modal],
  templateUrl: "./suppliers.html",
})
export class Suppliers {
  readonly t = inject(Language).translate;
  readonly message = inject(Language).message;
  readonly locale = inject(Language).locale;
  s = inject(Store);
  rows = signal<Supplier[]>([]);
  selected = signal<number | null>(null);
  supplier = computed(() => this.rows().find(row => row.id === this.selected()));
  loading = signal(true);
  error = signal("");
  saving = signal(false);
  supplierForm = signal<SupplierForm | null>(null);
  editingId: number | null = null;
  offerForm = signal<{ sku: string; unit_cost: number; available_qty: number | null } | null>(null);
  editingOffer = false;

  constructor() {
    if (this.s.warehouse()) void this.load();
  }

  private async load() {
    try {
      this.rows.set(await this.s.request<Supplier[]>("/suppliers"));
      this.selected.set(this.rows()[0]?.id ?? null);
    } catch (error) {
      this.error.set((error as Error).message);
    } finally {
      this.loading.set(false);
    }
  }

  openSupplier(supplier?: Supplier) {
    this.error.set("");
    this.editingId = supplier?.id ?? null;
    this.supplierForm.set(supplier
      ? { name: supplier.name, location: supplier.location, agreement: supplier.agreement,
          agreement_active: supplier.agreement_active, lead_days: supplier.lead_days }
      : { name: "", location: "", agreement: "", agreement_active: false, lead_days: 7 });
  }

  openOffer(offer?: Offer) {
    this.error.set("");
    this.editingOffer = !!offer;
    this.offerForm.set(offer
      ? { sku: offer.sku, unit_cost: offer.unit_cost, available_qty: offer.available_qty }
      : { sku: "", unit_cost: 1, available_qty: null });
  }

  async saveSupplier(form: SupplierForm) {
    const path = this.editingId ? "/suppliers/" + this.editingId : "/suppliers";
    if (await this.save(path, this.editingId ? "PUT" : "POST", form)) this.supplierForm.set(null);
  }

  async saveOffer(form: { sku: string; unit_cost: number; available_qty: number | null }) {
    const { sku, ...details } = form;
    if (await this.save("/suppliers/" + this.selected() + "/offers/" + encodeURIComponent(sku), "PUT", details)) {
      this.offerForm.set(null);
    }
  }

  private async save(path: string, method: string, data: unknown) {
    if (this.saving()) return false;
    this.saving.set(true);
    this.error.set("");
    try {
      const supplier = await this.s.request<Supplier>(path, method, data);
      this.rows.update(rows => [...rows.filter(row => row.id !== supplier.id), supplier]
        .sort((a, b) => a.name.localeCompare(b.name)));
      this.selected.set(supplier.id);
      return true;
    } catch (error) {
      this.error.set((error as Error).message);
      return false;
    } finally {
      this.saving.set(false);
    }
  }
}
