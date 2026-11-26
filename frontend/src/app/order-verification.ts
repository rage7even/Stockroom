import { DatePipe } from "@angular/common";
import { Component, effect, inject, input, output, signal, untracked } from "@angular/core";
import { BarcodeScan, ScanResult } from "./barcode-scan";
import { Language } from "./language";
import { newRequestId } from "./request-id";
import { Store } from "./store";

interface Verification {
  status: string;
  complete: boolean;
  latest_active_id: string | null;
  lines: { sku: string; product_name: string; location: string; expected: number; verified: number }[];
  history: {
    id: string; sku: string; barcode: string; staff: string; created_at: string;
    source: "camera" | "manual" | "demo"; voided_at: string | null; voided_by: string | null;
  }[];
}

const sources = { camera: "Camera", manual: "Manual / USB", demo: "Demo" };

@Component({
  selector: "sr-order-verification",
  imports: [BarcodeScan, DatePipe],
  templateUrl: "./order-verification.html",
})
export class OrderVerification {
  readonly message = inject(Language).message;
  readonly locale = inject(Language).locale;
  readonly orderId = input.required<string>();
  readonly status = input.required<string>();
  readonly changed = output<Verification>();
  readonly t = inject(Language).translate;
  readonly s = inject(Store);
  readonly snapshot = signal<Verification | null>(null);
  readonly busy = signal(false);
  readonly error = signal("");
  readonly retry = signal<(ScanResult & { request_id: string }) | null>(null);
  readonly sources = sources;

  constructor() {
    effect(() => {
      const id = this.orderId();
      untracked(() => {
        this.snapshot.set(null);
        this.retry.set(null);
        void this.run(id);
      });
    });
  }

  scan(result: ScanResult) {
    const scan = { ...result, request_id: newRequestId() };
    this.retry.set(scan);
    void this.run(this.orderId(), "", scan);
  }

  retryScan() {
    const retry = this.retry();
    if (retry) void this.run(this.orderId(), "", retry);
  }

  undo(scanId: string) {
    void this.run(this.orderId(), "/" + scanId + "/undo", {});
  }

  refresh() {
    void this.run(this.orderId());
  }

  private async run(orderId: string, suffix = "", body?: object) {
    this.busy.set(true);
    this.error.set("");
    try {
      const progress = await this.s.request<Verification>(
        "/orders/" + encodeURIComponent(orderId) + "/verification" + suffix,
        body ? "POST" : "GET",
        body,
      );
      if (this.orderId() !== orderId) return;
      if (body && !suffix) this.retry.set(null);
      this.snapshot.set(progress);
      this.changed.emit(progress);
    } catch (error) {
      if (this.orderId() !== orderId) return;
      const message = (error as Error).message;
      if (body && !suffix && !message.startsWith("Cannot connect") && !message.startsWith("Server error")) {
        this.retry.set(null);
      }
      this.error.set(message);
    } finally {
      if (this.orderId() === orderId) this.busy.set(false);
    }
  }
}
