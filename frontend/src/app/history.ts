import { Component, inject, signal, computed } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { DatePipe } from "@angular/common";
import { Store } from "./store";
import { Icon } from "./icon";

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

}
