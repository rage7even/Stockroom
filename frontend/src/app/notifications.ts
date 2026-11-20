import { DatePipe } from "@angular/common";
import { Component, DestroyRef, HostListener, effect, inject, signal } from "@angular/core";
import { Router } from "@angular/router";
import { Icon } from "./icon";
import { Store } from "./store";

interface StockNotification {
  id: number;
  message: string;
  created_at: string;
  read: boolean;
  sku: string | null;
  purchase_id: number | null;
}

@Component({
  selector: "sr-notifications",
  imports: [DatePipe, Icon],
  template: `
    <button class="icon-button notification-button" type="button" [attr.aria-expanded]="open()"
      aria-controls="notification-list" (click)="toggle()" title="Notifications"
      [attr.aria-label]="'Notifications, ' + unread() + ' unread'">
      <sr-icon name="bell" />
      @if(unread()){<span>{{unread()}}</span>}
    </button>
    @if(open()){
      <section class="notification-menu" id="notification-list" aria-label="Notifications">
        <div class="notification-heading">
          <h2>Notifications</h2>
          <button class="icon-button" type="button" aria-label="Close notifications" (click)="open.set(false)"><sr-icon name="close" /></button>
        </div>
        @if(error()){<p role="alert">{{error()}}</p>}
        @for(item of rows(); track item.id){
          <button class="notification-item" [class.unread]="!item.read" type="button" (click)="select(item)">
            <span>{{item.message}}</span><small>{{item.created_at | date:'dd MMM, HH:mm'}}{{item.read ? '' : ' · Unread'}}</small>
          </button>
        } @empty {<p>No notifications yet.</p>}
      </section>
    }
  `,
})
export class Notifications {
  private store = inject(Store);
  private router = inject(Router);
  private destroyRef = inject(DestroyRef);
  private revision = 0;
  open = signal(false);
  unread = signal(0);
  rows = signal<StockNotification[]>([]);
  error = signal("");

  constructor() {
    effect(() => {
      this.store.stockRevision();
      void this.load();
    });
    const timer = setInterval(() => void this.load(), 20000);
    this.destroyRef.onDestroy(() => {
      clearInterval(timer);
      ++this.revision;
    });
  }

  toggle() {
    this.open.update(open => !open);
    if (this.open()) void this.load();
  }

  @HostListener("document:keydown.escape")
  close() {
    this.open.set(false);
  }

  async load() {
    const revision = ++this.revision;
    try {
      const response = await this.store.request<{ unread: number; items: StockNotification[] }>("/notifications");
      if (revision !== this.revision) return;
      this.rows.set(response.items);
      this.unread.set(response.unread);
      this.error.set("");
    } catch (error) {
      if (revision === this.revision) this.error.set((error as Error).message);
    }
  }

  async select(item: StockNotification) {
    try {
      if (!item.read) await this.store.request("/notifications/" + item.id + "/read", "POST");
      this.open.set(false);
      void this.load();
      if (item.purchase_id) void this.router.navigate(["/purchases"], { queryParams: { order: item.purchase_id } });
      else if (item.sku) void this.router.navigate(["/products"], { queryParams: { sku: item.sku } });
    } catch (error) {
      this.error.set((error as Error).message);
    }
  }
}
