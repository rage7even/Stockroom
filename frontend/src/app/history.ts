import { Component, inject, signal, computed } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { DatePipe } from "@angular/common";
import { Store } from "./store";
import { Icon } from "./icon";
import { exportCsv } from "./export";
@Component({
  standalone: true,
  imports: [FormsModule, DatePipe, Icon],
  templateUrl: "./history.html",
})
export class History {
  s = inject(Store);
  query = signal("");
  type = signal("all");
  types = [
    "delivery_in",
    "reserve",
    "release",
    "sale",
    "correction",
    "write_off",
  ];
  filtered = computed(() =>
    this.s
      .movements()
      .filter(
        (m) =>
          (this.type() === "all" || m.movement_type === this.type()) &&
          `${m.sku} ${m.product_name} ${m.staff_name} ${m.note} ${m.order_id || ""}`
            .toLowerCase()
            .includes(this.query().toLowerCase()),
      ),
  );
  export() {
    exportCsv(
      "stockroom-history.csv",
      [
        "UTC time",
        "Staff",
        "SKU",
        "Type",
        "Shelf delta",
        "Reserved delta",
        "Source",
        "Order",
        "Note",
      ],
      this.filtered().map((m) => [
        m.moved_at,
        m.staff_name,
        m.sku,
        m.movement_type,
        m.physical_delta,
        m.reserved_delta,
        m.source,
        m.order_id,
        m.note,
      ]),
    );
  }
}
