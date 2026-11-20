from rest_framework import serializers
from .models import Product, Customer


class Integer(serializers.IntegerField):
    def to_internal_value(self, value):
        if type(value) is not int:
            raise serializers.ValidationError("Enter a whole number.")
        return super().to_internal_value(value)


class ProductInput(serializers.ModelSerializer):
    sku = serializers.RegexField(r"^[A-Z]{3}-[A-Z0-9]{2,12}-[A-Z]{3}$")
    price_kzt = Integer(min_value=1, max_value=10000000)
    reorder_level = Integer(min_value=0, max_value=100000)
    category = serializers.ChoiceField(
        choices=["Chargers", "Cables", "Cases", "Power banks", "Audio", "Adapters"]
    )

    class Meta:
        model = Product
        fields = [
            "sku",
            "product_name",
            "brand",
            "category",
            "price_kzt",
            "reorder_level",
            "location",
        ]


class CustomerInput(serializers.ModelSerializer):
    phone = serializers.RegexField(r"^\+?[0-9 ()-]{7,25}$")

    class Meta:
        model = Customer
        fields = ["shop_name", "contact_name", "phone"]


class LineInput(serializers.Serializer):
    sku = serializers.CharField()
    qty = Integer(min_value=1, max_value=100000)


class OrderInput(serializers.Serializer):
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), source="customer"
    )
    channel = serializers.ChoiceField(choices=["website", "sales_manager"])
    note = serializers.CharField(
        required=False, allow_blank=True, max_length=500, default=""
    )
    lines = LineInput(many=True, allow_empty=False, max_length=50)

    def validate_lines(self, lines):
        if len({line["sku"] for line in lines}) != len(lines):
            raise serializers.ValidationError("Each product may appear once per order.")
        return lines


class MovementInput(serializers.Serializer):
    sku = serializers.CharField()
    quantity = Integer(min_value=-100000, max_value=100000)
    source = serializers.ChoiceField(choices=["manual", "scanner"])
    note = serializers.CharField(min_length=3, max_length=300)
