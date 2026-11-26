import {Injectable,signal,computed} from '@angular/core';
export interface User {
 staff_id:number;full_name:string;login:string;role:string;
 shop_id:number|null;shop_name:string|null;phone:string;job_title:string;avatar:string;
}
export interface Product {sku:string;barcode:string;product_name:string;brand:string;category:string;price_kzt:number;qty_in_stock:number;reserved:number;available:number;defective:number;reorder_level:number;location:string}
export interface Customer {customer_id:number;shop_name:string;contact_name:string;phone:string}
export interface OrderLine {sku:string;product_name:string;qty_reserved:number;unit_price_kzt:number}
export interface Order {order_id:string;customer_id:number;shop_name:string;channel:string;status:string;confirmed_at:string;staff_name:string;note:string;stale:boolean;total_kzt:number;lines:OrderLine[]}
export interface Movement {movement_id:number;sku:string;product_name:string;movement_type:string;physical_delta:number;reserved_delta:number;moved_at:string;staff_name:string;source:string;note:string;order_id:string|null}
export interface CartData {
  id: string | null;
  version: string | null;
  customer_id: number | null;
  channel: string;
  note: string;
  lines: { sku: string; qty: number }[];
}
@Injectable({providedIn:'root'})
export class Store {
 user=signal<User|null>(null);products=signal<Product[]>([]);customers=signal<Customer[]>([]);orders=signal<Order[]>([]);movements=signal<Movement[]>([]);
 ready=signal(false);busy=signal(false);error=signal('');toast=signal('');
 cart=signal<CartData|null>(null);
 stockRevision=signal(0);
 warehouse=computed(()=>['manager','admin'].includes(this.user()?.role||''));
 support=computed(()=>this.user()?.role === 'tech_support');
 supplier=computed(()=>this.user()?.role === 'supplier');
 staffChat=computed(()=>!!this.user() && !this.supplier() && !this.user()?.shop_id);
 lowStock=computed(()=>this.products().filter(p=>p.available<p.reorder_level));
 openOrders=computed(()=>this.orders().filter(o=>['confirmed','packed'].includes(o.status)));
 staleOrders=computed(()=>this.openOrders().filter(o=>o.stale));
 async request<T>(path:string,method='GET',body?:unknown):Promise<T>{
  if(method!=='GET'&&!document.cookie.includes('csrftoken='))await this.request('/auth/csrf');
  const token=document.cookie.split('; ').find(c=>c.startsWith('csrftoken='))?.split('=')[1]||'';
  let response:Response;
  const multipart = body instanceof FormData;
  const headers: Record<string, string> = {'X-CSRFToken': decodeURIComponent(token)};
  if (!multipart) headers['Content-Type'] = 'application/json';
  try{response=await fetch('/api'+path,{method,credentials:'same-origin',headers,body:multipart?body:JSON.stringify(body)});}
  catch{throw new Error('Cannot connect. Start the Python server first.');}
  if (response.status === 204) return undefined as T;
  if(!response.headers.get('content-type')?.includes('application/json'))throw new Error('Server error. See the Python terminal.');
  const data=await response.json();
  if(!response.ok){
   if(data.detail==='Authentication credentials were not provided.')this.user.set(null);
   throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data));
  }
  return data;
 }
 async initialize(){
  try{await this.request('/auth/csrf');this.user.set(await this.request<User>('/auth/me'));await this.refresh();}
  catch(e){if(this.user())this.error.set((e as Error).message);}
  finally{this.ready.set(true);}
 }
 async refresh(){
  if (this.support() || this.supplier()) return;
  this.products.set(await this.request<Product[]>('/products'));
  this.customers.set(await this.request<Customer[]>('/customers'));
  this.orders.set(await this.request<Order[]>('/orders'));
  this.movements.set(this.warehouse()?await this.request<Movement[]>('/movements'):[]);
  this.cart.set(await this.request<CartData>('/cart'));
  this.stockRevision.update(revision => revision + 1);
 }
 async addToCart(sku: string) {
  if (this.busy()) return;
  this.busy.set(true);
  this.error.set('');
  try {
   this.cart.set(await this.request<CartData>('/cart', 'POST', { sku }));
   this.notify('Added to cart');
  } catch (error) {
   this.error.set((error as Error).message);
  } finally {
   this.busy.set(false);
  }
 }
 async findBarcode(code: string) {
  return this.request<Product>("/products/barcode?code=" + encodeURIComponent(code));
 }
 async mutate(path:string,body:unknown,message:string,method='POST'){
  if(this.busy())return false;
  this.busy.set(true);this.error.set('');
  try{await this.request(path,method,body);await this.refresh();this.notify(message);return true;}
  catch(e){this.error.set((e as Error).message);return false;}
  finally{this.busy.set(false);}
 }
 notify(message:string){this.toast.set(message);setTimeout(()=>this.toast.set(''),4000);}
 async logout(){
  try{await this.request('/auth/logout','POST');this.user.set(null);this.products.set([]);this.orders.set([]);this.customers.set([]);this.movements.set([]);this.cart.set(null);}
  catch(e){this.error.set((e as Error).message);}
 }
}
