import { Injectable, signal, computed } from "@angular/core";

export interface User {
  staff_id: number;
  full_name: string;
  login: string;
  role: string;
  is_active?: number;
}
export interface Product {
  sku: string;
  product_name: string;
  brand: string;
  category: string;
  price_kzt: number;
  qty_in_stock: number;
  reserved: number;
  available: number;
  reorder_level: number;
  location: string;
}
export interface Customer {
  customer_id: number;
  shop_name: string;
  contact_name: string;
  phone: string;
}
export interface OrderLine {
  sku: string;
  qty_reserved: number;
  unit_price_kzt: number;
  product_name: string;
}
export interface Order {
  order_id: string;
  customer_id: number;
  shop_name: string;
  channel: string;
  status: string;
  confirmed_at: string;
  staff_name: string;
  note: string;
  stale: boolean;
  total_kzt: number;
  lines: OrderLine[];
}
export interface Movement {
  movement_id: number;
  sku: string;
  product_name: string;
  movement_type: string;
  physical_delta: number;
  reserved_delta: number;
  moved_at: string;
  staff_name: string;
  source: string;
  note: string;
  order_id: string | null;
}
export interface Backup {
  name: string;
  size_bytes: number;
  created_at: string;
}

@Injectable({ providedIn: "root" })
export class Store {
  user = signal<User | null>(null);
  products = signal<Product[]>([]);
  customers = signal<Customer[]>([]);
  orders = signal<Order[]>([]);
  movements = signal<Movement[]>([]);
  staff = signal<User[]>([]);
  backups = signal<Backup[]>([]);
  ready = signal(false);
  busy = signal(false);
  error = signal("");
  toast = signal("");
  warehouse = computed(() =>
    ["manager", "admin"].includes(this.user()?.role || ""),
  );
  lowStock = computed(() =>
    this.products().filter((p) => p.available < p.reorder_level),
  );
  openOrders = computed(() =>
    this.orders().filter((o) => ["confirmed", "packed"].includes(o.status)),
  );
  staleOrders = computed(() => this.openOrders().filter((o) => o.stale));
  async request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
    let response: Response;
    try {
      response = await fetch("/api" + path, {
        method,
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new Error(
        "Cannot reach the Stockroom server. Check that Python is running and try again.",
      );
    }
    if (!response.headers.get("content-type")?.includes("application/json"))
      throw new Error(
        "The Stockroom API is unavailable. Start the Python server and use http://127.0.0.1:8000.",
      );
    const data = await response.json();
    if (!response.ok) {
      if (response.status === 401 && !path.includes("/auth/"))
        this.user.set(null);
      const detail = Array.isArray(data.detail)
        ? data.detail
            .map((x: any) => x.loc.slice(1).join(".") + ": " + x.msg)
            .join("; ")
        : data.detail;
      throw new Error(detail || "The request could not be completed");
    }
    return data as T;
  }
  async syncInventory() {
    if (!this.user() || this.busy()) return;
    const [products, orders] = await Promise.all([
      this.request<Product[]>("/products"),
      this.request<Order[]>("/orders"),
    ]);
    this.products.set(products);
    this.orders.set(orders);
  }
  async initialize() {
    try {
      this.user.set(await this.request<User>("/auth/me"));
      await this.refresh();
    } catch (e) {
      if (this.user()) this.error.set((e as Error).message);
    } finally {
      this.ready.set(true);
    }
  }
  async refresh() {
    const [products, customers, orders] = await Promise.all([
      this.request<Product[]>("/products"),
      this.request<Customer[]>("/customers"),
      this.request<Order[]>("/orders"),
    ]);
    this.products.set(products);
    this.customers.set(customers);
    this.orders.set(orders);
    if (this.warehouse())
      this.movements.set(await this.request<Movement[]>("/movements"));
    else this.movements.set([]);
    if (this.user()?.role === "admin") {
      const [staff, backups] = await Promise.all([
        this.request<User[]>("/staff"),
        this.request<Backup[]>("/backups"),
      ]);
      this.staff.set(staff);
      this.backups.set(backups);
    } else {
      this.staff.set([]);
      this.backups.set([]);
    }
  }
  async mutate(path: string, body: unknown, message: string, method = "POST") {
    if (this.busy()) return false;
    this.busy.set(true);
    this.error.set("");
    try {
      await this.request(path, method, body);
      await this.refresh();
      this.notify(message);
      return true;
    } catch (e) {
      this.error.set((e as Error).message);
      return false;
    } finally {
      this.busy.set(false);
    }
  }
  notify(message: string) {
    this.toast.set(message);
    setTimeout(() => this.toast.set(""), 4500);
  }
  async logout() {
    try {
      await this.request("/auth/logout", "POST");
      this.user.set(null);
      this.products.set([]);
      this.orders.set([]);
      this.customers.set([]);
      this.movements.set([]);
      this.staff.set([]);
      this.backups.set([]);
    } catch (e) {
      this.error.set((e as Error).message);
    }
  }
}
