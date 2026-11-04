import { Component, inject, signal, computed } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { DecimalPipe, DatePipe } from "@angular/common";
import { ActivatedRoute } from "@angular/router";
import { Store, Product } from "./store";
import { Icon } from "./icon";
import { Modal } from "./modal";
import { exportCsv } from "./export";
import qrcode from "qrcode-generator";
@Component({
  standalone: true,
  imports: [FormsModule, DecimalPipe, DatePipe, Icon, Modal],
  templateUrl: "./products.html",
})
export class Products {
  s = inject(Store);
  route = inject(ActivatedRoute);
  query = signal("");
  category = signal("all");
  stock = signal("all");
  sort = signal("name");
  detail = signal("");
  editor = signal(false);
  editing = "";
  categories = [
    "Chargers",
    "Cables",
    "Cases",
    "Power banks",
    "Audio",
    "Adapters",
  ];
  form = {
    sku: "",
    product_name: "",
    brand: "",
    category: "Chargers",
    price_kzt: 1000,
    reorder_level: 5,
    location: "",
  };
  selected = computed(() =>
    this.s.products().find((p) => p.sku === this.detail()),
  );
  productHistory = computed(() =>
    this.s
      .movements()
      .filter((m) => m.sku === this.detail())
      .slice(0, 8),
  );
  outCount = computed(
    () => this.s.products().filter((p) => p.available === 0).length,
  );
  filtered = computed(() =>
    this.s
      .products()
      .filter(
        (p) =>
          (this.category() === "all" || p.category === this.category()) &&
          (this.stock() === "all" ||
            (this.stock() === "low" && p.available < p.reorder_level) ||
            (this.stock() === "out" && p.available === 0)) &&
          `${p.product_name} ${p.sku} ${p.brand}`
            .toLowerCase()
            .includes(this.query().toLowerCase()),
      )
      .sort((a, b) =>
        this.sort() === "stock"
          ? a.available - b.available
          : this.sort() === "price"
            ? a.price_kzt - b.price_kzt
            : a.product_name.localeCompare(b.product_name),
      ),
  );
  constructor() {
    this.route.queryParamMap.subscribe((p) =>
      this.stock.set(
        ["low", "out"].includes(p.get("stock") || "") ? p.get("stock")! : "all",
      ),
    );
  }
  reset() {
    this.query.set("");
    this.category.set("all");
    this.stock.set("all");
  }
  icon(c: string) {
    return c === "Chargers" || c === "Cables"
      ? "cable"
      : c === "Audio"
        ? "audio"
        : c === "Power banks"
          ? "power"
          : "phone";
  }
  openEditor(p?: Product) {
    this.editing = p?.sku || "";
    this.form = p
      ? {
          sku: p.sku,
          product_name: p.product_name,
          brand: p.brand,
          category: p.category,
          price_kzt: p.price_kzt,
          reorder_level: p.reorder_level,
          location: p.location,
        }
      : {
          sku: "",
          product_name: "",
          brand: "",
          category: "Chargers",
          price_kzt: 1000,
          reorder_level: 5,
          location: "",
        };
    this.s.error.set("");
    this.editor.set(true);
  }
  async save() {
    if (
      await this.s.mutate(
        "/products" + (this.editing ? "/" + this.editing : ""),
        this.form,
        "Product saved",
        this.editing ? "PUT" : "POST",
      )
    )
      this.editor.set(false);
  }
  export() {
    exportCsv(
      "stockroom-products.csv",
      [
        "SKU",
        "Product",
        "Category",
        "Price KZT",
        "On shelf",
        "Reserved",
        "Available",
        "Location",
      ],
      this.filtered().map((p) => [
        p.sku,
        p.product_name,
        p.category,
        p.price_kzt,
        p.qty_in_stock,
        p.reserved,
        p.available,
        p.location,
      ]),
    );
  }
  print(p: Product) {
    const w = window.open("", "_blank", "width=600,height=450");
    if (!w) {
      this.s.error.set("Allow popups to print a shelf label");
      return;
    }
    w.document.title = "Stockroom shelf label";
    for (const text of [
      p.product_name,
      p.sku,
      "Shelf: " + p.location,
      p.price_kzt + " KZT",
    ]) {
      const el = w.document.createElement("h2");
      el.textContent = text;
      w.document.body.appendChild(el);
    }
    const qr = qrcode(0, "M");
    qr.addData(p.sku);
    qr.make();
    const image = w.document.createElement("img");
    image.alt = "SKU QR code";
    image.src = qr.createDataURL(5);
    w.document.body.appendChild(image);
    image.onload = () => w.print();
  }
}
