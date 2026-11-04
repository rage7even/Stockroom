"""Validate JSON with Django Forms, including strict integers and unknown fields."""
from django import forms
from django.core.exceptions import ValidationError


class StrictIntegerField(forms.IntegerField):
    def to_python(self, value):
        if type(value) is not int:
            raise ValidationError('Enter a whole number.')
        return super().to_python(value)


class TextField(forms.CharField):
    def to_python(self, value):
        if value is not None and not isinstance(value, str):
            raise ValidationError('Enter a string.')
        return super().to_python(value)


class ChoiceField(TextField):
    def __init__(self, values, **kwargs):
        self.values = values
        super().__init__(**kwargs)

    def validate(self, value):
        super().validate(value)
        if value not in self.values:
            raise ValidationError('Choose a valid value.')


class PatternField(TextField):
    def __init__(self, pattern, **kwargs):
        from django.core.validators import RegexValidator
        super().__init__(validators=[RegexValidator(pattern)], **kwargs)


class InputForm(forms.Form):
    def clean(self):
        data = super().clean()
        unknown = set(self.data) - set(self.fields)
        if unknown:
            raise ValidationError('Unknown fields: ' + ', '.join(sorted(unknown)))
        return data


class LoginForm(InputForm):
    login = TextField(min_length=3, max_length=150)
    password = TextField(min_length=1, max_length=128)


class RegistrationForm(LoginForm):
    full_name = TextField(min_length=2, max_length=80)
    password = TextField(min_length=10, max_length=128)

    def clean_login(self):
        value = self.cleaned_data['login'].lower()
        if '@' not in value or '.' not in value.split('@')[-1]:
            raise ValidationError('Enter a valid email address.')
        return value


class ProductForm(InputForm):
    sku = PatternField(r'^[A-Z]{3}-[A-Z0-9]{2,12}-[A-Z]{3}$')
    product_name = TextField(min_length=2, max_length=100)
    brand = TextField(min_length=2, max_length=40)
    category = ChoiceField(['Chargers', 'Cables', 'Cases', 'Power banks', 'Audio', 'Adapters'])
    price_kzt = StrictIntegerField(min_value=1, max_value=10000000)
    reorder_level = StrictIntegerField(min_value=0, max_value=100000)
    location = TextField(min_length=1, max_length=30)


class CustomerForm(InputForm):
    shop_name = TextField(min_length=2, max_length=80)
    contact_name = TextField(min_length=2, max_length=80)
    phone = PatternField(r'^\+?[0-9 ()-]{7,25}$')


class OrderLineForm(InputForm):
    sku = TextField()
    qty = StrictIntegerField(min_value=1, max_value=100000)


class OrderForm(InputForm):
    customer_id = StrictIntegerField(min_value=1)
    channel = ChoiceField(['website', 'sales_manager'])
    note = TextField(required=False, max_length=500)
    lines = forms.JSONField()

    def clean_lines(self):
        lines = self.cleaned_data['lines']
        if not isinstance(self.data.get('lines'), list) or not isinstance(lines, list) or not 1 <= len(lines) <= 50:
            raise ValidationError('An order needs between 1 and 50 lines.')
        result = []
        for index, line in enumerate(lines):
            if not isinstance(line, dict):
                raise ValidationError(f'Line {index + 1} must be an object.')
            form = OrderLineForm(line)
            if not form.is_valid():
                raise ValidationError(f'Line {index + 1}: {form.errors.as_text()}')
            result.append(form.cleaned_data)
        if len({line['sku'] for line in result}) != len(result):
            raise ValidationError('Each SKU may appear only once in an order.')
        return result


class MovementForm(InputForm):
    sku = TextField()
    quantity = StrictIntegerField(min_value=-100000, max_value=100000)
    source = ChoiceField(['manual', 'scanner'])
    note = TextField(min_length=3, max_length=300)


class StaffUpdateForm(InputForm):
    role = ChoiceField(['sales', 'manager', 'admin'])
    is_active = StrictIntegerField(min_value=0, max_value=1)
