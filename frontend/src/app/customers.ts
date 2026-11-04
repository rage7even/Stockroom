import { Component, inject, signal, computed } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { DecimalPipe } from "@angular/common";
import { Store } from "./store";
import { Icon } from "./icon";
import { Modal } from "./modal";
@Component({
  standalone: true,
  imports: [FormsModule, DecimalPipe, Icon, Modal],
  templateUrl: "./customers.html",
})
export class Customers {
  s = inject(Store);
  query = signal("");
  creating = signal(false);
  form = { shop_name: "", contact_name: "", phone: "" };
  filtered = computed(() =>
    this.s
      .customers()
      .filter((c) =>
        `${c.shop_name} ${c.contact_name} ${c.phone}`
          .toLowerCase()
          .includes(this.query().toLowerCase()),
      ),
  );
  orderCount(id: number) {
    return this.s.orders().filter((o) => o.customer_id === id).length;
  }
  value(id: number) {
    return this.s
      .orders()
      .filter((o) => o.customer_id === id && o.status === "shipped")
      .reduce((n, o) => n + o.total_kzt, 0);
  }
  open() {
    this.form = { shop_name: "", contact_name: "", phone: "" };
    this.s.error.set("");
    this.creating.set(true);
  }
  async save() {
    if (await this.s.mutate("/customers", this.form, "Customer added"))
      this.creating.set(false);
  }
}
