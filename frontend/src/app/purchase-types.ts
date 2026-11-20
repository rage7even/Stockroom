export interface Offer {
  sku: string;
  product_name: string;
  unit_cost: number;
  available_qty: number | null;
  updated_at: string;
}

export interface SupplierForm {
  name: string;
  location: string;
  agreement: string;
  agreement_active: boolean;
  lead_days: number;
}

export interface Supplier extends SupplierForm {
  id: number;
  offers: Offer[];
}

export interface PurchaseLine {
  sku: string;
  product_name: string;
  ordered: number;
  received: number;
  remaining: number;
  unit_cost: number;
}

export interface Receipt {
  id: string;
  created_at: string;
  staff_name: string;
  lines: { sku: string; qty: number }[];
}

export type PurchaseStatus = "ordered" | "in_transit" | "partial" | "received";

export interface Purchase {
  id: number;
  supplier_id: number;
  supplier_name: string;
  status: PurchaseStatus;
  created_at: string;
  expected_on: string;
  lines: PurchaseLine[];
  receipts: Receipt[];
}

export const purchaseStatus: Record<PurchaseStatus, string> = {
  ordered: "Ordered", in_transit: "In transit", partial: "Partially received", received: "Received",
};
