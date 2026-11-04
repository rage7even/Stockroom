import { Component, inject, signal, computed } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { DatePipe } from "@angular/common";
import { Store } from "./store";
import { Icon } from "./icon";
@Component({
  standalone: true,
  imports: [FormsModule, DatePipe, Icon],
  templateUrl: "./receiving.html",
})
export class Receiving {
  s = inject(Store);
  mode = signal("receive");
  sku = "";
  quantity = 1;
  source = "manual";
  note = "";
  confirmed = false;
  product() {
    return this.s.products().find((p) => p.sku === this.sku);
  }
  recent = computed(() =>
    this.s
      .movements()
      .filter((m) => m.movement_type === "delivery_in")
      .slice(0, 5),
  );
  async submit() {
    if (!this.confirmed) {
      this.confirmed = true;
      return;
    }
    if (
      await this.s.mutate(
        "/stock/" + this.mode(),
        {
          sku: this.sku,
          quantity: this.quantity,
          source: this.source,
          note: this.note,
        },
        "Stock updated and recorded in history",
      )
    ) {
      this.quantity = 1;
      this.note = "";
      this.confirmed = false;
      document.getElementById("scan-field")?.focus();
    }
  }
}
