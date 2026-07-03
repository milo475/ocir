from django import forms

from .models import Order


class OrderCreateForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['customer_name', 'phone', 'address']
        labels = {
            'customer_name': 'Нэр',
            'phone': 'Утасны дугаар',
            'address': 'Хүргэлтийн хаяг',
        }
        widgets = {
            'customer_name': forms.TextInput(attrs={'placeholder': 'Таны нэр'}),
            'phone': forms.TextInput(attrs={'placeholder': '99112233'}),
            'address': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Дүүрэг, хороо, байр, орц, тоот...',
            }),
        }
