# billing-service

A deliberately small billing service, used to try out an idea.

`src/refund.py` records refunds. `src/api.py` is the inbound HTTP layer; every
inbound request carries a `request_id` the client assigns and reuses on retry.

Run the tests with `python3 -m unittest discover -s tests`.
