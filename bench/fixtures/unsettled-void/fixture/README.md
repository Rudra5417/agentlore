# billing-service

Order cancellation and refunds for the checkout service.

Payments go through the provider client in `src/provider.py`. A `charge()` creates a
transaction; transactions settle in the provider's nightly batch, after which the money has
actually moved.

```bash
python3 -m unittest discover -s tests
```
