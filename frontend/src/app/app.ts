import { Component, inject, signal, OnDestroy } from "@angular/core";
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
export class App implements OnDestroy {
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
  timer: ReturnType<typeof setInterval>;
  constructor() {
    void this.s.initialize();
    this.timer = setInterval(() => {
      if (document.visibilityState === "visible")
        void this.s.syncInventory().catch((e) => this.s.error.set(e.message));
    }, 10000);
  }
  ngOnDestroy() {
    clearInterval(this.timer);
  }
}
