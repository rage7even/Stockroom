import { DOCUMENT, registerLocaleData } from "@angular/common";
import kk from "@angular/common/locales/kk";
import ru from "@angular/common/locales/ru";
import { Component, inject, Injectable, signal } from "@angular/core";
import { translations, systemMessages } from "./translations";

registerLocaleData(ru);
registerLocaleData(kk);

type Locale = "en" | "ru" | "kk";
type Parameter = string | number | null | undefined;

const labels: Record<string, string> = {
  admin: "Admin", manager: "Manager", sales: "Sales", supplier: "Supplier", tech_support: "Tech Support",
  confirmed: "Confirmed", packed: "Packed", shipped: "Shipped", cancelled: "Cancelled",
  pending: "Pending", received: "Received", rejected: "Rejected", all: "All",
  open: "Open", in_progress: "In progress", resolved: "Resolved",
  delivery_in: "Delivery in", reserve: "Reservation", release: "Release", sale: "Sale",
  correction: "Stock correction", write_off: "Write-off", store_return: "Return", purchase_receipt: "Purchase receipt",
  manual: "Manual entry", scan: "Barcode scanner", barcode: "Barcode scanner", camera: "Camera", system: "System",
};

const fields: Record<string, string> = {
  full_name: "Full name", job_title: "Job title", login: "Email address", email: "Email address",
  password: "Password", current_password: "Current password", old_code: "Code from your current recovery email", code: "Reset code", sku: "SKU", product_name: "Product name", category: "Category",
  brand: "Brand", location: "Location", price_kzt: "Price (KZT)", reorder_level: "Reorder threshold",
  customer_id: "Customer", shop_name: "Shop name", contact_name: "Contact name", phone: "Phone",
  lines: "Order lines", qty: "Quantity", quantity: "Quantity", note: "Note", channel: "Channel",
  name: "Name", lead_days: "Lead time in days", available_qty: "Available at supplier", unit_cost: "Unit cost",
  supplier_id: "Supplier", agreement: "Agreement terms", agreement_active: "Active agreement",
  good: "Sellable", defective: "Defective", reason: "Reason", comment: "Comment",
  title: "Title", description: "Description", attachment: "Photo or screenshot (optional)", photo: "Photo",
  body: "Message", barcode: "Barcode", status: "Status", purchase: "Purchase order number",
};

function localeOf(value: string | null): Locale {
  return value === "ru" || value === "kk" ? value : "en";
}

function fieldName(field: string): string {
  return fields[field] ?? field.replaceAll("_", " ");
}

@Injectable({ providedIn: "root" })
export class Language {
  private readonly root = inject(DOCUMENT).documentElement;
  private readonly current = signal<Locale>(this.read());
  readonly locale = this.current.asReadonly();

  constructor() {
    this.updateDocument();
  }

  readonly translate = (text: string, ...values: Parameter[]): string => {
    const locale = this.current();
    const format = locale === "en" ? text : translations[text]?.[locale === "ru" ? 0 : 1] ?? text;
    return values.length ? format.replace(/\{(\d+)\}/g, (_, index) => String(values[Number(index)] ?? "")) : format;
  };

  readonly label = (code: string | null | undefined): string => {
    return code ? this.translate(labels[code] ?? code) : "";
  };

  readonly message = (text: string): string => {
    if (!text) return "";
    if (text.startsWith("{") || text.startsWith("[")) {
      try {
        const messages = this.details(JSON.parse(text));
        if (messages.length) return messages.join(" · ");
      } catch {
        // A bracket can also start a plain text message.
      }
    }
    const direct = this.translate(text);
    if (direct !== text || this.current() === "en") return direct;
    for (const [pattern, key] of systemMessages) {
      const match = pattern.exec(text);
      if (!match) continue;
      const values = match.slice(1);
      if (key === "Row {0}: {1}") values[1] = this.message(values[1]);
      if (key === "{0} must be a whole number.") values[0] = this.translate(fieldName(values[0]));
      if (key === "The password is too similar to the {0}.") values[0] = this.translate(values[0]);
      return this.translate(key, ...values);
    }
    return this.translate("An error occurred. Please check the form and try again.");
  };

  private details(value: unknown): string[] {
    if (typeof value === "string") return [this.message(value)];
    if (Array.isArray(value)) return value.flatMap(entry => this.details(entry));
    if (value && typeof value === "object") {
      return Object.entries(value).flatMap(([field, entry]) => this.details(entry).map(detail =>
        field === "detail" || field === "non_field_errors" ? detail : this.translate(fieldName(field)) + ": " + detail,
      ));
    }
    return [];
  }

  choose(value: string) {
    const locale = localeOf(value);
    this.current.set(locale);
    this.updateDocument();
    try {
      localStorage.setItem("stockroom-language", locale);
    } catch {
      // The selected language remains active for this session.
    }
  }

  private updateDocument() {
    this.root.lang = this.current();
    this.root.ownerDocument.title = this.translate("Stockroom — inventory, in sync");
  }

  private read(): Locale {
    try {
      return localeOf(localStorage.getItem("stockroom-language"));
    } catch {
      return "en";
    }
  }
}


@Component({
  selector: "sr-language-select",
  template: `
    <select class="language-select" [attr.aria-label]="language.translate('Language')"
      [value]="language.locale()" (change)="language.choose($any($event.target).value)">
      <option value="en" lang="en">EN</option>
      <option value="ru" lang="ru">РУ</option>
      <option value="kk" lang="kk">ҚАЗ</option>
    </select>
  `,
})
export class LanguageSelect {
  readonly language = inject(Language);
}
