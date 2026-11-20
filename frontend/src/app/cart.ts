import { DecimalPipe } from "@angular/common";
import { Component, computed, inject, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Router, RouterLink } from "@angular/router";
import { Icon } from "./icon";
import { CartData, Store } from "./store";

@Component({
  standalone: true,
  imports: [DecimalPipe, FormsModule, RouterLink, Icon],
  templateUrl: "./cart.html",
})
export class Cart {
  s = inject(Store);
  private router = inject(Router);
  private saved = signal<CartData | null>(null);
  lines = signal<{ sku: string; qty: number | null }[]>([]);
  busy = signal(false);
  error = signal("");
  loaded = signal(false);
  dirty = signal(false);
  customerId: number | null = null;
  channel = "sales_manager";
  note = "";
  rows = computed(() => {
    const products = new Map(this.s.products().map(product => [product.sku, product]));
    return this.lines().map(line => ({ ...line, product: products.get(line.sku) }));
  });
  total = computed(() =>
    this.rows().reduce((sum, row) => sum + (row.qty ?? 0) * (row.product?.price_kzt ?? 0), 0)
  );
  valid = computed(() => this.rows().every(row =>
    row.product && Number.isInteger(row.qty) && row.qty! >= 1 && row.qty! <= 100000
  ));

  constructor() {
    void this.load();
  }

  async load() {
    this.busy.set(true);
    this.error.set("");
    try {
      const cart = await this.s.request<CartData>("/cart");
      this.accept(cart);
      this.loaded.set(true);
    } catch (error) {
      this.error.set((error as Error).message);
    } finally {
      this.busy.set(false);
    }
  }

  private accept(cart: CartData) {
    this.saved.set(cart);
    this.s.cart.set(cart);
    this.lines.set(cart.lines);
    this.customerId = cart.customer_id;
    this.channel = cart.channel;
    this.note = cart.note;
    this.dirty.set(false);
  }

  edit(sku: string, qty: number | null) {
    this.lines.update(lines => lines.map(line => line.sku === sku ? { sku, qty } : line));
    this.dirty.set(true);
  }

  remove(sku: string) {
    this.lines.update(lines => lines.filter(line => line.sku !== sku));
    this.dirty.set(true);
  }

  async submit(checkout: boolean) {
    let cart = this.saved();
    if (this.busy() || this.s.busy() || !cart?.id || !this.valid()) return;
    this.busy.set(true);
    this.error.set("");
    try {
      if (this.dirty()) {
        cart = await this.s.request<CartData>("/cart", "PUT", {
          version: cart.version,
          customer_id: this.customerId,
          channel: this.channel,
          note: this.note,
          lines: this.lines(),
        });
        this.accept(cart);
      }
      if (!checkout) {
        this.s.notify("Cart saved");
        return;
      }
      const order = await this.s.request<{ order_id: string }>(
        "/cart/" + cart.id + "/checkout", "POST", { version: cart.version },
      );
      this.accept({ ...cart, id: null, version: null, lines: [] });
      this.s.notify("Order confirmed. Stock reserved.");
      await this.router.navigate(["/orders"], { queryParams: { order: order.order_id } });
      await this.s.refresh();
    } catch (error) {
      const message = (error as Error).message;
      if (this.saved()?.id) this.error.set(message);
      else this.s.error.set(message);
    } finally {
      this.busy.set(false);
    }
  }
}
