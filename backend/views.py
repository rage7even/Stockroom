from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import F, Prefetch
from django.http import FileResponse, JsonResponse
from django.utils import timezone

from backend.api import APIError, endpoint, payload, rate_limit, set_session, staff_data
from backend.backup import backup_directory, create_backup
from backend.forms import LoginForm, RegistrationForm, ProductForm, CustomerForm, OrderForm, MovementForm, StaffUpdateForm
from backend.models import Staff, Session, Product, Customer, Order, OrderItem, StockMovement
from backend.security import hash_password, verify_password, token_hash

USERS = ('sales', 'manager', 'admin')
WAREHOUSE = ('manager', 'admin')
ADMIN = ('admin',)
PRODUCT_FIELDS = ('sku', 'product_name', 'brand', 'category', 'price_kzt', 'qty_in_stock', 'reorder_level', 'location', 'is_active', 'reserved', 'available')


def stamp(value):
    return value.isoformat(timespec='seconds')


@endpoint(['GET'])
def health(request):
    return {'status': 'ok', 'version': '1.0.0'}


@endpoint(['POST'])
def login(request):
    rate_limit(request)
    data = payload(request, LoginForm)
    with transaction.atomic():
        staff = Staff.objects.filter(login=data['login'], is_active=1).first()
        if staff is None or not verify_password(data['password'], staff.password_hash):
            raise APIError(401, 'Incorrect email or password')
        # Upgrade legacy hashes after a successful login without changing the password.
        if ':' in staff.password_hash and '$' not in staff.password_hash:
            staff.password_hash = hash_password(data['password'])
            staff.save(update_fields=['password_hash'])
        response = JsonResponse(staff_data(staff))
        set_session(response, staff)
    return response


@endpoint(['POST'])
def register(request):
    rate_limit(request)
    data = payload(request, RegistrationForm)
    with transaction.atomic():
        staff = Staff.objects.create(full_name=data['full_name'], login=data['login'],
                                     password_hash=hash_password(data['password']), role='sales')
        response = JsonResponse(staff_data(staff), status=201)
        set_session(response, staff)
    return response


@endpoint(['GET'], USERS)
def me(request):
    return staff_data(request.staff, active=True)


@endpoint(['POST'])
def logout(request):
    Session.objects.filter(token_hash=token_hash(request.COOKIES.get('stockroom_session', ''))).delete()
    response = JsonResponse({'ok': True})
    response.delete_cookie('stockroom_session', path='/', samesite='Strict')
    return response


@endpoint(['GET', 'POST'], USERS)
def products(request):
    if request.method == 'GET':
        return list(Product.objects.inventory().filter(is_active=1).order_by('product_name').values(*PRODUCT_FIELDS))
    require_warehouse(request)
    data = payload(request, ProductForm)
    Product.objects.create(**data)
    return JsonResponse({'sku': data['sku']}, status=201)


def require_warehouse(request):
    if request.staff.role not in WAREHOUSE:
        raise APIError(403, 'Only managers and admins can change stock')


@endpoint(['PUT'], WAREHOUSE)
def edit_product(request, sku):
    data = payload(request, ProductForm)
    if data.pop('sku') != sku:
        raise APIError(422, 'A product SKU is permanent')
    if Product.objects.filter(pk=sku).update(**data) != 1:
        raise APIError(404, 'Product not found')
    return {'ok': True}


@endpoint(['GET', 'POST'], USERS)
def customers(request):
    if request.method == 'GET':
        return list(Customer.objects.order_by('shop_name').values())
    customer = Customer.objects.create(**payload(request, CustomerForm))
    return JsonResponse({'customer_id': customer.pk}, status=201)


def movement(sku, kind, physical, reserved, staff, note, order=None, source='system'):
    StockMovement.objects.create(sku_id=sku, movement_type=kind, physical_delta=physical,
                                 reserved_delta=reserved, staff=staff, note=note, order=order, source=source)


@endpoint(['GET', 'POST'], USERS)
def orders(request):
    if request.method == 'GET':
        result = []
        rows = Order.objects.select_related('customer', 'staff').prefetch_related(
            Prefetch('lines', queryset=OrderItem.objects.select_related('sku').order_by('item_id')),
        ).order_by('-confirmed_at', '-order_id')
        for row in rows:
            lines = [
                {'item_id': line.pk, 'order_id': row.pk, 'sku': line.sku_id,
                 'qty_reserved': line.qty_reserved, 'unit_price_kzt': line.unit_price_kzt,
                 'confirmed_at': stamp(line.confirmed_at), 'product_name': line.sku.product_name}
                for line in row.lines.all()
            ]
            result.append({
                'order_id': row.pk, 'customer_id': row.customer_id, 'channel': row.channel,
                'status': row.status, 'confirmed_at': stamp(row.confirmed_at), 'updated_at': stamp(row.updated_at),
                'staff_id': row.staff_id, 'note': row.note, 'shop_name': row.customer.shop_name,
                'staff_name': row.staff.full_name, 'lines': lines,
                'total_kzt': sum(line['qty_reserved'] * line['unit_price_kzt'] for line in lines),
                'stale': row.status in ('confirmed', 'packed') and row.confirmed_at < timezone.now() - timedelta(days=14),
            })
        return result
    return confirm_order(request, payload(request, OrderForm))


def confirm_order(request, data):
    with transaction.atomic():
        if not Customer.objects.filter(pk=data['customer_id']).exists():
            raise APIError(422, 'Choose an existing customer')
        checked = []
        for line in data['lines']:
            product = Product.objects.inventory().filter(pk=line['sku'], is_active=1).first()
            if product is None:
                raise APIError(422, f"Unknown product: {line['sku']}")
            if line['qty'] > product.available:
                raise APIError(409, f"Only {product.available} units of {line['sku']} are available. Nothing was reserved.")
            checked.append((line, product.price_kzt))
        year = timezone.now().year
        prefix = f'ORD-{year}-'
        # Also tolerate gaps in imported order IDs.
        sequence = max((int(oid[len(prefix):]) for oid in Order.objects.filter(pk__startswith=prefix).values_list('pk', flat=True)
                        if oid[len(prefix):].isdigit()), default=0) + 1
        order = Order.objects.create(order_id=f'{prefix}{sequence:04d}', customer_id=data['customer_id'],
                                     channel=data['channel'], status='confirmed', staff=request.staff, note=data['note'])
        for line, price in checked:
            OrderItem.objects.create(order=order, sku_id=line['sku'], qty_reserved=line['qty'],
                                     unit_price_kzt=price, confirmed_at=order.confirmed_at)
            movement(line['sku'], 'reserve', 0, line['qty'], request.staff, 'Order confirmed', order)
    return JsonResponse({'order_id': order.pk}, status=201)


@endpoint(['POST'], WAREHOUSE)
def transition(request, oid, action):
    targets = {'pack': 'packed', 'ship': 'shipped', 'cancel': 'cancelled'}
    if action not in targets:
        raise APIError(404, 'Unknown action')
    with transaction.atomic():
        order = Order.objects.filter(pk=oid).first()
        if order is None:
            raise APIError(404, 'Order not found')
        if order.status not in ('confirmed', 'packed') or action == 'pack' and order.status != 'confirmed':
            raise APIError(409, 'This order has already moved past this step')
        if action != 'pack':
            for line in order.lines.all():
                qty = line.qty_reserved
                if action == 'ship':
                    Product.objects.filter(pk=line.sku_id).update(qty_in_stock=F('qty_in_stock') - qty)
                movement(line.sku_id, 'sale' if action == 'ship' else 'release', -qty if action == 'ship' else 0,
                         -qty, request.staff, 'Order shipped' if action == 'ship' else 'Order cancelled — reservation released', order)
        order.status = targets[action]
        order.updated_at = timezone.now()
        order.save(update_fields=['status', 'updated_at'])
    return {'ok': True, 'status': targets[action]}


@endpoint(['POST'], WAREHOUSE)
def change_stock(request, action):
    if action not in ('receive', 'adjust'):
        raise APIError(404, 'Unknown stock action')
    data = payload(request, MovementForm)
    qty = data['quantity']
    if qty == 0 or action == 'receive' and qty < 1:
        raise APIError(422, 'Enter a positive receipt quantity or a non-zero correction')
    with transaction.atomic():
        product = Product.objects.inventory().filter(pk=data['sku'], is_active=1).first()
        if product is None:
            raise APIError(404, 'SKU not found. Scan again or enter it manually.')
        if product.available + qty < 0:
            raise APIError(409, 'Correction would remove reserved stock. Cancel the affected orders first.')
        Product.objects.filter(pk=product.pk).update(qty_in_stock=F('qty_in_stock') + qty)
        movement(product.pk, 'delivery_in' if action == 'receive' else 'correction', qty, 0,
                 request.staff, data['note'], source=data['source'])
    return {'ok': True}


@endpoint(['GET'], WAREHOUSE)
def history(request):
    return [
        {'movement_id': row.pk, 'sku': row.sku_id, 'movement_type': row.movement_type,
         'physical_delta': row.physical_delta, 'reserved_delta': row.reserved_delta,
         'moved_at': stamp(row.moved_at), 'staff_id': row.staff_id, 'order_id': row.order_id,
         'source': row.source, 'note': row.note, 'product_name': row.sku.product_name, 'staff_name': row.staff.full_name}
        for row in StockMovement.objects.select_related('sku', 'staff').order_by('-moved_at', '-pk')
    ]


@endpoint(['GET'], ADMIN)
def list_staff(request):
    return [staff_data(staff, active=True) for staff in Staff.objects.order_by('pk')]


@endpoint(['PATCH'], ADMIN)
def update_staff(request, staff_id):
    data = payload(request, StaffUpdateForm)
    if staff_id == request.staff.pk:
        raise APIError(409, 'You cannot change your own access')
    with transaction.atomic():
        if Staff.objects.filter(pk=staff_id).update(**data) != 1:
            raise APIError(404, 'Staff account not found')
        Session.objects.filter(staff_id=staff_id).delete()
    return {'ok': True}


@endpoint(['GET', 'POST'], ADMIN)
def backups(request):
    if request.method == 'POST':
        return JsonResponse({'name': create_backup().name}, status=201)
    return [{'name': p.name, 'size_bytes': p.stat().st_size,
             'created_at': datetime.fromtimestamp(p.stat().st_mtime, dt_timezone.utc).isoformat()}
            for p in sorted(backup_directory().glob('stockroom-*.db'), reverse=True)]


@endpoint(['GET'], ADMIN)
def download_backup(request, name):
    if Path(name).name != name or not name.startswith('stockroom-') or not name.endswith('.db'):
        raise APIError(400, 'Invalid backup name')
    path = backup_directory() / name
    if not path.is_file():
        raise APIError(404, 'Backup not found')
    return FileResponse(path.open('rb'), as_attachment=True, filename=name, content_type='application/octet-stream')


@endpoint(['GET'])
def frontend(request, path=''):
    root = (settings.BASE_DIR / 'frontend' / 'dist' / 'stockroom' / 'browser').resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise APIError(404, 'File not found')
    if not path or not target.is_file() and '.' not in Path(path).name:
        target = root / 'index.html'
    if not target.is_file():
        raise APIError(404, 'Frontend build is missing. Run npm.cmd run build in frontend.')
    return FileResponse(target.open('rb'))


def api_not_found(request, **kwargs):
    return JsonResponse({'detail': 'Not found'}, status=404)
