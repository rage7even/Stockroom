import { Component, inject, signal, computed, effect, untracked } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { DecimalPipe, DatePipe } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { Store, Order } from "./store";
import { Icon } from "./icon";
import { Modal } from "./modal";
import { newRequestId } from "./request-id";
import { Language } from "./language";
import { OrderVerification } from "./order-verification";

interface Draft {
  id: string;
  customer_id: number | null;
  channel: string;
  note: string;
  lines: { sku: string; qty: number | null }[];
}

interface ReturnRecord {
  id: number;
  sku: string;
  good: number;
  defective: number;
  reason: string;
  comment: string;
  staff: string;
  created_at: string;
  status: "pending" | "received" | "rejected";
}

@Component({
  standalone: true,
  imports: [FormsModule, DecimalPipe, DatePipe, Icon, Modal, RouterLink, OrderVerification],
  templateUrl: "./orders.html",
})
export class Orders {
  readonly label = inject(Language).label;
  readonly message = inject(Language).message;
  readonly locale = inject(Language).locale;
  s = inject(Store);
  readonly t = inject(Language).translate;
  readonly verified = signal(false);
  route = inject(ActivatedRoute);
  query = signal("");
  status = signal("all");
  creating = signal(false);
  detail = signal("");
  private requestedOrder = signal("");
  pending = signal("");
  tabs = [
    { value: "all", name: "All orders" },
    { value: "confirmed", name: "Confirmed" },
    { value: "packed", name: "Packed" },
    { value: "shipped", name: "Shipped" },
    { value: "cancelled", name: "Cancelled" },
    { value: "stale", name: "Ageing" },
  ];
  customerId: number | null = null;
  channel = "sales_manager";
  note = "";
  lines: Draft["lines"] = [{ sku: "", qty: 1 }];
  draftId = "";
  drafts = signal<Draft[]>([]);
  draftStatus = signal("");
  private saving = Promise.resolve(false);
  returnRecords = signal<ReturnRecord[]>([]);
  returnForm = { sku: "", good: 0, defective: 0, reason: "", comment: "", request_id: "" };
  selected = computed(() =>
    this.s.orders().find((o) => o.order_id === this.detail()),
  );
  filtered = computed(() =>
    this.s
      .orders()
      .filter(
        (o) =>
          (this.status() === "all" ||
            (this.status() === "stale" && o.stale) ||
            o.status === this.status()) &&
          `${o.order_id} ${o.shop_name}`
            .toLowerCase()
            .includes(this.query().toLowerCase()),
      ),
  );
  constructor() {
    void this.loadDrafts();
    this.route.queryParamMap.subscribe((p) => {
      this.status.set(p.get("status") === "stale" ? "stale" : "all");
      this.requestedOrder.set(p.get("order") ?? "");
      if (p.get("create")) this.openCreate();
    });
    effect(() => {
      const id = this.requestedOrder();
      if (!id) return;
      const order = this.s.orders().find(row => row.order_id === id);
      if (order) {
        this.requestedOrder.set("");
        untracked(() => this.openOrder(order));
      }
    });
  }
  statusLabel(status: string) {
    return this.tabs.find(tab => tab.value === status)?.name ?? status;
  }
  count(status: string) {
    return this.s
      .orders()
      .filter(
        (o) =>
          status === "all" ||
          (status === "stale" && o.stale) ||
          o.status === status,
      ).length;
  }
  available(sku: string) {
    return this.s.products().find((p) => p.sku === sku)?.available || 0;
  }
  total() {
    return this.lines.reduce(
      (n, l) =>
        n +
        (this.s.products().find((p) => p.sku === l.sku)?.price_kzt || 0) *
          (l.qty || 0),
      0,
    );
  }
  openCreate() {
    this.openDraft();
  }
  openDraft(draft?: Draft) {
    this.draftId = draft?.id ?? newRequestId();
    this.draftStatus.set(draft ? "Draft saved" : "");
    this.customerId = draft?.customer_id ?? this.s.user()?.shop_id ?? null;
    this.lines = draft?.lines.map(line => ({ ...line })) ?? [{ sku: "", qty: 1 }];
    this.note = draft?.note ?? "";
    this.channel = draft?.channel ?? "sales_manager";
    this.s.error.set("");
    this.creating.set(true);
  }
  async loadDrafts() {
    try {
      this.drafts.set(await this.s.request<Draft[]>("/drafts"));
    } catch (error) {
      this.s.error.set((error as Error).message);
    }
  }
  private orderData() {
    return {
      customer_id: this.customerId,
      channel: this.channel,
      note: this.note,
      lines: this.lines.map(line => ({ ...line })),
    };
  }
  queueDraft() {
    const id = this.draftId;
    const data = this.orderData();
    for (const line of data.lines) {
      if (!Number.isInteger(line.qty) || (line.qty ?? 0) < 1 || (line.qty ?? 0) > 100000) {
        line.qty = null;
      }
    }
    this.draftStatus.set("Saving draft…");
    this.saving = this.saving.then(async () => {
      try {
        await this.s.request("/drafts/" + id, "PUT", data);
        this.drafts.update(rows => [{ id, ...data }, ...rows.filter(row => row.id !== id)]);
        if (id === this.draftId) this.draftStatus.set("Draft saved");
        return true;
      } catch (error) {
        if (id === this.draftId) this.draftStatus.set((error as Error).message);
        return false;
      }
    });
    return this.saving;
  }
  async saveAndClose() {
    if (await this.queueDraft()) this.creating.set(false);
  }
  async discardDraft(draft: Draft) {
    await this.saving;
    if (await this.s.mutate("/drafts/" + draft.id, undefined, "Draft discarded", "DELETE")) {
      this.drafts.update(rows => rows.filter(row => row.id !== draft.id));
    }
  }
  async submit() {
    const id = this.draftId;
    const data = this.orderData();
    if (!(await this.queueDraft()) || id !== this.draftId) return;
    if (
      await this.s.mutate(
        "/drafts/" + id + "/confirm",
        data,
        "Order confirmed. Stock reserved.",
      )
    ) {
      this.drafts.update(rows => rows.filter(row => row.id !== id));
      this.creating.set(false);
    }
  }
  openOrder(order: Order) {
    this.verified.set(false);
    this.pending.set("");
    this.detail.set(order.order_id);
    this.s.error.set("");
    this.returnRecords.set([]);
    this.resetReturn(order.lines[0]?.sku ?? "");
    if (order.status === "shipped" && (this.s.warehouse() || this.s.user()?.shop_id)) {
      void this.loadReturns(order.order_id);
    }
  }
  private resetReturn(sku: string) {
    this.returnForm = { sku, good: 0, defective: 0, reason: "", comment: "", request_id: newRequestId() };
  }
  private async loadReturns(orderId: string) {
    try {
      const records = await this.s.request<ReturnRecord[]>("/returns/" + orderId);
      if (this.detail() === orderId) this.returnRecords.set(records);
    } catch (error) {
      if (this.detail() === orderId) this.s.error.set((error as Error).message);
    }
  }
  remainingReturn(order: Order, sku: string) {
    const shipped = order.lines.find(line => line.sku === sku)?.qty_reserved ?? 0;
    return shipped - this.returnRecords().filter(item => item.sku === sku && item.status !== "rejected")
      .reduce((total, item) => total + item.good + item.defective, 0);
  }
  async submitReturn(order: Order) {
    const sku = this.returnForm.sku;
    if (await this.s.mutate("/returns/" + order.order_id, this.returnForm, "Return request sent")) {
      await this.loadReturns(order.order_id);
      this.resetReturn(sku);
    }
  }
  async reviewReturn(order: Order, item: ReturnRecord, status: "received" | "rejected") {
    const path = "/returns/" + order.order_id + "/" + item.id + "/review";
    if (await this.s.mutate(path, { status }, status === "received" ? "Return received" : "Return rejected")) {
      await this.loadReturns(order.order_id);
    }
  }
  verificationChanged(order: Order, result: { complete: boolean; status: string }) {
    this.verified.set(result.complete);
    if (order.status !== result.status) {
      this.pending.set("");
      this.s.orders.update(rows => rows.map(row => row.order_id === order.order_id ? { ...row, status: result.status } : row));
    }
  }
  async transition(o: Order) {
    if (
      await this.s.mutate(
        "/orders/" + o.order_id + "/" + this.pending(),
        {},
        "Order updated",
      )
    )
      this.pending.set("");
    if (this.selected()?.status === "shipped") await this.loadReturns(o.order_id);
  }
}
