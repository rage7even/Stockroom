import { DatePipe } from "@angular/common";
import { Component, DestroyRef, computed, inject, signal } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { FormsModule } from "@angular/forms";
import { ActivatedRoute, Router } from "@angular/router";
import { Language } from "./language";
import { newRequestId } from "./request-id";
import { Store } from "./store";

type ChatMode = "purchase" | "staff";

interface ChatEntry {
  id: number;
  label: string;
  detail: string;
  role?: boolean;
}

interface Message {
  id: number;
  sender_id: number;
  sender: string;
  body: string;
  created_at: string;
}

interface MessagePage {
  messages: Message[];
  more: boolean;
}

const roleNames: Record<string, string> = {
  manager: "Manager", admin: "Admin", sales: "Sales", tech_support: "Tech Support",
};

@Component({
  imports: [FormsModule, DatePipe],
  templateUrl: "./purchase-chat.html",
})
export class PurchaseChat {
  readonly message = inject(Language).message;
  readonly locale = inject(Language).locale;
  readonly s = inject(Store);
  readonly t = inject(Language).translate;
  readonly canPurchase = computed(() => this.s.warehouse() || this.s.supplier());
  readonly mode = signal<ChatMode>("purchase");
  readonly conversations = signal<ChatEntry[]>([]);
  readonly current = signal<number | null>(null);
  readonly threadTitle = computed(() => {
    const id = this.current();
    if (this.mode() === "purchase") return "PO-" + id;
    return this.conversations().find(row => row.id === id)?.label ?? this.t("Staff chat");
  });
  readonly messages = signal<Message[]>([]);
  readonly more = signal(false);
  readonly listBusy = signal(false);
  readonly messagesBusy = signal(false);
  readonly sending = signal(false);
  readonly listError = signal("");
  readonly readError = signal("");
  readonly error = signal("");
  supplier = "";
  purchase = "";
  employee = "";
  draft = "";
  private pending: { path: string; body: string; id: string } | null = null;
  private threadVersion = 0;
  private listVersion = 0;
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly destroy = inject(DestroyRef);

  constructor() {
    if (!this.canPurchase() && !this.s.staffChat()) return;
    this.route.queryParamMap.pipe(takeUntilDestroyed()).subscribe(params => {
      const mode = this.s.staffChat() && (!this.canPurchase() || params.get("mode") === "staff" || params.has("staff"))
        ? "staff" : "purchase";
      if (!this.listVersion || mode !== this.mode()) {
        this.mode.set(mode);
        this.conversations.set([]);
        void this.loadList(mode);
      }
      const value = Number(params.get(mode === "staff" ? "staff" : "purchase"));
      const id = Number.isSafeInteger(value) && value > 0 ? value : null;
      this.threadVersion++;
      this.current.set(id);
      this.messages.set([]);
      this.error.set("");
      this.readError.set("");
      this.more.set(false);
      this.messagesBusy.set(false);
      this.sending.set(false);
      this.draft = "";
      if (id) void this.loadMessages("initial");
    });
    const timer = setInterval(() => {
      if (!document.hidden && !this.readError()) void this.loadMessages("newer");
    }, 5000);
    this.destroy.onDestroy(() => clearInterval(timer));
  }

  choose(id: number | null) {
    this.navigate(this.mode(), id);
  }

  switchMode(mode: ChatMode) {
    if (mode !== this.mode()) this.navigate(mode, null);
  }

  private navigate(mode: ChatMode, id: number | null) {
    const queryParams = mode === "staff"
      ? { mode: "staff", staff: id }
      : { purchase: id };
    void this.router.navigate([], { relativeTo: this.route, queryParams });
  }

  async applyFilters() {
    if (!this.listBusy()) await this.loadList(this.mode(), true);
  }

  private async loadList(mode: ChatMode, clearSelection = false) {
    const version = ++this.listVersion;
    this.listBusy.set(true);
    this.listError.set("");
    try {
      let rows: ChatEntry[];
      if (mode === "purchase") {
        const params = new URLSearchParams({ supplier: this.supplier.trim(), purchase: this.purchase.trim() });
        const purchases = await this.s.request<{ id: number; supplier_name: string }[]>("/chat?" + params);
        rows = purchases.map(row => ({ id: row.id, label: "PO-" + row.id, detail: row.supplier_name }));
      } else {
        const params = new URLSearchParams({ name: this.employee.trim() });
        const staff = await this.s.request<{ id: number; name: string; role: string }[]>("/chat/staff?" + params);
        rows = staff.map(row => ({ id: row.id, label: row.name, detail: roleNames[row.role] ?? row.role, role: true }));
      }
      if (version !== this.listVersion) return;
      this.conversations.set(rows);
      if (clearSelection && this.current() && !rows.some(row => row.id === this.current())) this.choose(null);
    } catch (error) {
      if (version === this.listVersion) this.listError.set((error as Error).message);
    } finally {
      if (version === this.listVersion) this.listBusy.set(false);
    }
  }

  clearFilters() {
    this.supplier = "";
    this.purchase = "";
    this.employee = "";
    void this.applyFilters();
  }

  private threadPath(id: number) {
    return "/chat/" + (this.mode() === "staff" ? "staff/" : "") + id + "/messages";
  }

  async loadMessages(direction: "initial" | "newer" | "older") {
    const id = this.current();
    if (!id || this.messagesBusy() || this.sending()) return;
    this.messagesBusy.set(true);
    const version = this.threadVersion;
    const messages = this.messages();
    const cursor = direction === "older" && messages.length ? "?before=" + messages[0].id
      : direction === "newer" && messages.length ? "?after=" + messages[messages.length - 1].id
      : "";
    try {
      const page = await this.s.request<MessagePage>(this.threadPath(id) + cursor);
      if (version !== this.threadVersion) return;
      this.merge(page.messages);
      if (!cursor || direction === "older") this.more.set(page.more);
      this.readError.set("");
    } catch (error) {
      if (version === this.threadVersion) this.readError.set((error as Error).message);
    } finally {
      if (version === this.threadVersion) this.messagesBusy.set(false);
    }
  }

  async send() {
    const id = this.current();
    const body = this.draft.trim();
    if (!id || !body || this.sending() || this.messagesBusy() || this.readError()) return;
    const path = this.threadPath(id);
    if (this.pending?.path !== path || this.pending?.body !== body) {
      this.pending = { path, body, id: newRequestId() };
    }
    const pending = this.pending;
    const version = this.threadVersion;
    this.sending.set(true);
    this.error.set("");
    try {
      await this.s.request<Message>(path, "POST", { body, request_id: pending.id });
      if (this.pending === pending) this.pending = null;
      if (version === this.threadVersion) {
        if (this.draft.trim() === body) this.draft = "";
        this.sending.set(false);
        await this.loadMessages("newer");
      }
    } catch (error) {
      if (version === this.threadVersion) this.error.set((error as Error).message);
    } finally {
      if (version === this.threadVersion) this.sending.set(false);
    }
  }

  private merge(rows: Message[]) {
    this.messages.update(messages => {
      const byId = new Map(messages.map(message => [message.id, message]));
      for (const row of rows) byId.set(row.id, row);
      return Array.from(byId.values()).sort((first, second) => first.id - second.id);
    });
  }
}
