import { Component, inject, signal } from "@angular/core";
import { RouterOutlet, RouterLink, RouterLinkActive } from "@angular/router";
import { DatePipe } from "@angular/common";
import { Store } from "./store";
import { Icon } from "./icon";
import { Auth } from "./auth";
@Component({
  selector: "app-root",
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, DatePipe, Icon, Auth],
  templateUrl: "./app.html",
})
export class App {
  s = inject(Store);
  mobile = signal(false);
  today = new Date();
  navigation = [
    { path: "/", label: "Overview", icon: "grid", restricted: false },
    { path: "/products", label: "Products", icon: "box", restricted: false },
    { path: "/orders", label: "Orders", icon: "orders", restricted: false },
    {
      path: "/receiving",
      label: "Receiving",
      icon: "receive",
      restricted: true,
    },
    {
      path: "/history",
      label: "Stock history",
      icon: "history",
      restricted: true,
    },
    {
      path: "/customers",
      label: "Customers",
      icon: "users",
      restricted: false,
    },
  ];
  async refresh(){try{await this.s.refresh();}catch(e){this.s.error.set((e as Error).message);}}
  constructor() { void this.s.initialize(); }
}
