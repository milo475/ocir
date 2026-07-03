from .models import ProductVariant


class Cart:
    """Session дээр хадгалагдах сагс: {variant_id(str): quantity(int)}."""

    SESSION_KEY = 'cart'

    def __init__(self, request):
        self.session = request.session
        self.cart = self.session.setdefault(self.SESSION_KEY, {})

    def save(self):
        # Session доторх dict-ийг шууд өөрчлөхөд Django мэдэхгүй тул
        # гараар тэмдэглэж өгнө.
        self.session.modified = True

    def add(self, variant, quantity):
        vid = str(variant.id)
        current = self.cart.get(vid, 0)
        self.cart[vid] = min(current + quantity, variant.stock)
        self.save()

    def set_quantity(self, variant, quantity):
        vid = str(variant.id)
        quantity = min(quantity, variant.stock)
        if quantity <= 0:
            self.cart.pop(vid, None)
        else:
            self.cart[vid] = quantity
        self.save()

    def remove(self, variant_id):
        self.cart.pop(str(variant_id), None)
        self.save()

    def clear(self):
        self.session[self.SESSION_KEY] = {}
        self.cart = self.session[self.SESSION_KEY]
        self.save()

    def __len__(self):
        return sum(self.cart.values())

    def items(self):
        """Сагсны мөрүүд: устгагдсан variant-уудыг session-оос цэвэрлэнэ."""
        variants = ProductVariant.objects.filter(
            id__in=self.cart.keys()
        ).select_related('product')
        found_ids = {str(v.id) for v in variants}

        stale = [vid for vid in self.cart if vid not in found_ids]
        for vid in stale:
            del self.cart[vid]
        if stale:
            self.save()

        rows = []
        for variant in variants:
            quantity = self.cart[str(variant.id)]
            price = variant.product.price
            rows.append({
                'variant': variant,
                'quantity': quantity,
                'price': price,
                'line_total': price * quantity,
            })
        return rows

    def total(self):
        return sum(row['line_total'] for row in self.items())
