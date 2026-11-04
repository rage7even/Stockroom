import { Component, inject, computed } from "@angular/core";
import { DecimalPipe } from "@angular/common";
import { RouterLink } from "@angular/router";
import { Store } from "./store";
import { Icon } from "./icon";
@Component({
  standalone: true,
  imports: [DecimalPipe, RouterLink, Icon],
  templateUrl: "./dashboard.html",
})
export class Dashboard {
  s = inject(Store);
  available = computed(() =>
    this.s.products().reduce((n, p) => n + p.available, 0),
  );
  reserved = computed(() =>
    this.s.products().reduce((n, p) => n + p.reserved, 0),
  );
  value = computed(() =>
    this.s.products().reduce((n, p) => n + p.qty_in_stock * p.price_kzt, 0),
  );
  outOfStock = computed(
    () => this.s.products().filter((p) => !p.available).length,
  );
  categories = computed(() =>
    ["Chargers", "Cables", "Cases", "Power banks", "Audio", "Adapters"].map(
      (name) => ({
        name,
        units: this.s
          .products()
          .filter((p) => p.category === name)
          .reduce((n, p) => n + p.available, 0),
      }),
    ),
  );
  maxCategory = computed(() =>
    Math.max(1, ...this.categories().map((c) => c.units)),
  );
  productIcon(c: string) {
    return c === "Cables" || c === "Chargers"
      ? "cable"
      : c === "Audio"
        ? "audio"
        : c === "Power banks"
          ? "power"
          : "phone";
  }
  categoryClass(c: string) {
    return c === "Chargers"
      ? "mint"
      : c === "Audio"
        ? "lavender"
        : c === "Cables"
          ? "sand"
          : "blue";
  }
}
