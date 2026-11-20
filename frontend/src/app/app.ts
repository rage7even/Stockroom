import { Component, inject, signal } from "@angular/core";
import { RouterOutlet, RouterLink, RouterLinkActive, Router } from "@angular/router";
import { DatePipe } from "@angular/common";
import { Store } from "./store";
import { effect } from "@angular/core";
import { Icon } from "./icon";
import { Auth } from "./auth";
import { Notifications } from "./notifications";
@Component({
  selector: "app-root",
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, DatePipe, Icon, Auth, Notifications],
  templateUrl: "./app.html",
})
export class App {
  s = inject(Store);
  router = inject(Router);
  mobile = signal(false);
  today = new Date();
  navigation = [
    { path: "/", label: "Overview", icon: "grid", restricted: false },
    { path: "/products", label: "Products", icon: "box", restricted: false },
    { path: "/cart", label: "Cart", icon: "cart", restricted: false },
    { path: "/orders", label: "Orders", icon: "orders", restricted: false },
    { path: "/suppliers", label: "Suppliers", icon: "users", restricted: true },
    { path: "/purchases", label: "Purchase orders", icon: "orders", restricted: true },
    { path: "/purchase-receiving", label: "Purchase receiving", icon: "scan", restricted: true },
    {
      path: "/receiving",
      label: "Receiving",
      icon: "receive",
      restricted: true,
    },
    { path: "/returns", label: "Returns & defects", icon: "return", restricted: true },
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
    { path: "/data", label: "Import / export", icon: "download", restricted: true },
    { path: "/issues", label: "Report issue", icon: "alert", restricted: false },
  ];
  async refresh(){try{await this.s.refresh();}catch(e){this.s.error.set((e as Error).message);}}
  constructor() {
    effect(() => {
      if (this.s.support() && !["/issues", "/profile"].includes(this.router.url.split("?")[0])) {
        void this.router.navigateByUrl("/issues");
      }
    });
    void this.s.initialize();
  }
}
