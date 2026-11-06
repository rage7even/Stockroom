import {Injectable,signal,computed} from '@angular/core';
export interface User {staff_id:number;full_name:string;login:string;role:string}
export interface Product {sku:string;product_name:string;brand:string;category:string;price_kzt:number;qty_in_stock:number;reserved:number;available:number;reorder_level:number;location:string}
export interface Customer {customer_id:number;shop_name:string;contact_name:string;phone:string}
export interface OrderLine {sku:string;product_name:string;qty_reserved:number;unit_price_kzt:number}
export interface Order {order_id:string;customer_id:number;shop_name:string;channel:string;status:string;confirmed_at:string;staff_name:string;note:string;stale:boolean;total_kzt:number;lines:OrderLine[]}
export interface Movement {movement_id:number;sku:string;product_name:string;movement_type:string;physical_delta:number;reserved_delta:number;moved_at:string;staff_name:string;source:string;note:string;order_id:string|null}
@Injectable({providedIn:'root'})
export class Store {
 user=signal<User|null>(null);products=signal<Product[]>([]);customers=signal<Customer[]>([]);orders=signal<Order[]>([]);movements=signal<Movement[]>([]);
 ready=signal(false);busy=signal(false);error=signal('');toast=signal('');
 warehouse=computed(()=>['manager','admin'].includes(this.user()?.role||''));
 lowStock=computed(()=>this.products().filter(p=>p.available<p.reorder_level));
 openOrders=computed(()=>this.orders().filter(o=>['confirmed','packed'].includes(o.status)));
 staleOrders=computed(()=>this.openOrders().filter(o=>o.stale));
 async request<T>(path:string,method='GET',body?:unknown):Promise<T>{
  if(method!=='GET'&&!document.cookie.includes('csrftoken='))await this.request('/auth/csrf');
  const token=document.cookie.split('; ').find(c=>c.startsWith('csrftoken='))?.split('=')[1]||'';
  let response:Response;
  try{response=await fetch('/api'+path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':decodeURIComponent(token)},body:body===undefined?undefined:JSON.stringify(body)});}
  catch{throw new Error('Cannot connect. Start the Python server first.');}
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
  this.products.set(await this.request<Product[]>('/products'));
  this.customers.set(await this.request<Customer[]>('/customers'));
  this.orders.set(await this.request<Order[]>('/orders'));
  this.movements.set(this.warehouse()?await this.request<Movement[]>('/movements'):[]);
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
  try{await this.request('/auth/logout','POST');this.user.set(null);this.products.set([]);this.orders.set([]);this.customers.set([]);this.movements.set([]);}
  catch(e){this.error.set((e as Error).message);}
 }
}
