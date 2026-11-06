import { Routes } from "@angular/router";
import { Dashboard } from "./dashboard";
import { Products } from "./products";
import { Orders } from "./orders";
import { Receiving } from "./receiving";
import { History } from "./history";
import { Customers } from "./customers";
export const routes: Routes = [
  { path: "", component: Dashboard },
  { path: "products", component: Products },
  { path: "orders", component: Orders },
  { path: "receiving", component: Receiving },
  { path: "history", component: History },
  { path: "customers", component: Customers },
  { path: "**", redirectTo: "" },
];
