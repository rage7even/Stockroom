import { Component, inject, signal, computed } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { DecimalPipe, DatePipe } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { Store, Order } from "./store";
import { Icon } from "./icon";
import { Modal } from "./modal";
@Component({
  standalone: true,
  imports: [FormsModule, DecimalPipe, DatePipe, Icon, Modal, RouterLink],
  templateUrl: "./orders.html",
})
export class Orders {
  s = inject(Store);
  route = inject(ActivatedRoute);
  query = signal("");
  status = signal("all");
  creating = signal(false);
  detail = signal("");
  pending = signal("");
  tabs = [
    { value: "all", name: "All orders" },
    { value: "confirmed", name: "Confirmed" },
    { value: "packed", name: "Packed" },
    { value: "shipped", name: "Shipped" },
    { value: "cancelled", name: "Cancelled" },
    { value: "stale", name: "Ageing" },
  ];
  customerId: number | null = null;
  channel = "sales_manager";
  note = "";
  lines = [{ sku: "", qty: 1 }];
  selected = computed(() =>
    this.s.orders().find((o) => o.order_id === this.detail()),
  );
  filtered = computed(() =>
    this.s
      .orders()
      .filter(
        (o) =>
          (this.status() === "all" ||
            (this.status() === "stale" && o.stale) ||
            o.status === this.status()) &&
          `${o.order_id} ${o.shop_name}`
            .toLowerCase()
            .includes(this.query().toLowerCase()),
      ),
  );
  constructor() {
    this.route.queryParamMap.subscribe((p) => {
      this.status.set(p.get("status") === "stale" ? "stale" : "all");
      if (p.get("create")) this.openCreate();
    });
  }
  count(status: string) {
    return this.s
      .orders()
      .filter(
        (o) =>
          status === "all" ||
          (status === "stale" && o.stale) ||
          o.status === status,
      ).length;
  }
  available(sku: string) {
    return this.s.products().find((p) => p.sku === sku)?.available || 0;
  }
  total() {
    return this.lines.reduce(
      (n, l) =>
        n +
        (this.s.products().find((p) => p.sku === l.sku)?.price_kzt || 0) *
          (l.qty || 0),
      0,
    );
  }
  openCreate() {
    this.customerId = null;
    this.lines = [{ sku: "", qty: 1 }];
    this.note = "";
    this.channel = "sales_manager";
    this.s.error.set("");
    this.creating.set(true);
  }
  async submit() {
    if (
      await this.s.mutate(
        "/orders",
        {
          customer_id: this.customerId,
          channel: this.channel,
          note: this.note,
          lines: this.lines,
        },
        "Order confirmed. Stock reserved.",
      )
    )
      this.creating.set(false);
  }
  async transition(o: Order) {
    if (
      await this.s.mutate(
        "/orders/" + o.order_id + "/" + this.pending(),
        {},
        "Order updated",
      )
    )
      this.pending.set("");
  }
}
