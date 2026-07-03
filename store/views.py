from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .cart import Cart
from .forms import OrderCreateForm
from .models import Category, Order, OrderItem, Product, ProductVariant


class OutOfStockError(Exception):
    def __init__(self, messages):
        self.messages = messages


def home(request):
    return render(request, 'store/home.html')


def product_list(request):
    categories = Category.objects.all()
    products = Product.objects.filter(is_active=True).select_related('category')

    active_slug = request.GET.get('category', '')
    if active_slug:
        products = products.filter(category__slug=active_slug)

    return render(request, 'store/product_list.html', {
        'categories': categories,
        'products': products,
        'active_slug': active_slug,
    })


def product_detail(request, pk):
    product = get_object_or_404(
        Product.objects.select_related('category'), pk=pk, is_active=True
    )
    variants = product.variants.all()
    variant_data = [
        {'id': v.id, 'size': v.size, 'color': v.color, 'stock': v.stock}
        for v in variants
    ]
    sizes = list(dict.fromkeys(v.size for v in variants))
    colors = list(dict.fromkeys(v.color for v in variants))

    return render(request, 'store/product_detail.html', {
        'product': product,
        'variant_data': variant_data,
        'sizes': sizes,
        'colors': colors,
    })


def _parse_quantity(value, default=1):
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


@require_POST
def cart_add(request):
    variant = get_object_or_404(
        ProductVariant, pk=request.POST.get('variant_id'), product__is_active=True
    )
    quantity = _parse_quantity(request.POST.get('quantity'))
    Cart(request).add(variant, quantity)
    return redirect('store:cart_detail')


@require_POST
def cart_update(request, variant_id):
    variant = get_object_or_404(ProductVariant, pk=variant_id)
    quantity = _parse_quantity(request.POST.get('quantity'), default=0)
    if 'remove' in request.POST:
        quantity = 0
    Cart(request).set_quantity(variant, quantity)
    return redirect('store:cart_detail')


def cart_detail(request):
    cart = Cart(request)
    return render(request, 'store/cart.html', {
        'items': cart.items(),
        'cart_total': cart.total(),
    })


@transaction.atomic
def _create_order(cart, form):
    # select_for_update: захиалга үүсэх хооронд өөр хүн ижил variant-ыг
    # зэрэг авахаас хамгаална (SQLite дээр нөлөөгүй ч Postgres дээр чухал).
    variants = (
        ProductVariant.objects.select_for_update()
        .filter(id__in=cart.cart.keys())
        .select_related('product')
    )

    problems = []
    for variant in variants:
        wanted = cart.cart[str(variant.id)]
        if variant.stock < wanted:
            problems.append(
                f'{variant}: үлдэгдэл {variant.stock}, та {wanted} захиалсан байна.'
            )
    if problems:
        raise OutOfStockError(problems)

    order = form.save(commit=False)
    order.total = 0
    order.save()

    total = 0
    for variant in variants:
        quantity = cart.cart[str(variant.id)]
        price = variant.product.price  # захиалгын мөчийн үнийг хуулна
        OrderItem.objects.create(
            order=order, variant=variant, quantity=quantity, price=price
        )
        variant.stock -= quantity
        variant.save(update_fields=['stock'])
        total += price * quantity

    order.total = total
    order.save(update_fields=['total'])
    cart.clear()
    return order


def checkout(request):
    cart = Cart(request)
    items = cart.items()
    if not items:
        return redirect('store:product_list')

    stock_errors = []
    if request.method == 'POST':
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            try:
                order = _create_order(cart, form)
            except OutOfStockError as e:
                stock_errors = e.messages
            else:
                request.session['last_order_id'] = order.id
                return redirect('store:payment')
    else:
        form = OrderCreateForm()

    return render(request, 'store/checkout.html', {
        'form': form,
        'items': items,
        'cart_total': cart.total(),
        'stock_errors': stock_errors,
    })


def payment(request):
    order_id = request.session.get('last_order_id')
    if not order_id:
        return redirect('store:product_list')
    order = get_object_or_404(Order, pk=order_id)
    return render(request, 'store/payment.html', {'order': order})


def order_success(request):
    order_id = request.session.get('last_order_id')
    if not order_id:
        return redirect('store:product_list')
    order = get_object_or_404(Order, pk=order_id)
    return render(request, 'store/order_success.html', {'order': order})
