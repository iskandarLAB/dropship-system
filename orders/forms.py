from django import forms

from .models import Order


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["customer_name", "customer_phone", "address", "postcode", "city", "state", "notes"]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = "form-select" if name == "state" else "form-control"
            field.widget.attrs.setdefault("class", css)
        self.fields["state"].widget.attrs["id"] = "id_state"

    def clean_postcode(self):
        pc = self.cleaned_data["postcode"].strip()
        if not (pc.isdigit() and len(pc) == 5):
            raise forms.ValidationError("Postcode must be 5 digits.")
        return pc


def parse_items(post):
    """Read the dynamic item rows from POST: item_variant / item_qty / item_price lists."""
    variants = post.getlist("item_variant")
    qtys = post.getlist("item_qty")
    prices = post.getlist("item_price")
    items, errors = [], []
    for idx, (v, q, p) in enumerate(zip(variants, qtys, prices), start=1):
        if not v:
            continue
        try:
            items.append({"variant_id": int(v), "qty": int(q), "sell_price": p or "0"})
            if int(q) <= 0:
                errors.append(f"Item {idx}: quantity must be at least 1.")
            float(p or 0)
        except ValueError:
            errors.append(f"Item {idx}: invalid quantity or price.")
    if not items:
        errors.append("Add at least one item.")
    return items, errors
