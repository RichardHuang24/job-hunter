# Billing

Billing is **off** unless you turn it on. With `BILLING_ENABLED=false` - the
default, and the right setting when you host Job Hunter for yourself -
every feature is free, nothing talks to Stripe, and the webhook answers
`404`.

What's built so far is the groundwork for the hosted version:

- the `BILLING_ENABLED` switch, and `GET /billing` (whether it's on, and
  whether the Stripe keys are set);
- Stripe's webhook, `POST /billing/webhook`. Each event's `Stripe-Signature`
  is checked against `STRIPE_WEBHOOK_SECRET` (and must be under five
  minutes old), then the event is recorded once in `billing_events` -
  Stripe resends, and a repeat is acknowledged but not stored twice
  (`app/billing.py`).

Plans, checkout, the customer portal and limits per plan come with the
hosted version ([roadmap.md](roadmap.md)). The recorded events are kept so
they can be applied then.

## Settings

| Setting | Meaning |
| --- | --- |
| `BILLING_ENABLED` | `false` (default): everything is free |
| `STRIPE_SECRET_KEY` | Your Stripe secret key - a test key (`sk_test_...`) in development |
| `STRIPE_WEBHOOK_SECRET` | The webhook's signing secret (`whsec_...`) |

## Trying it in development

The `stripe` service runs the [Stripe CLI](https://docs.stripe.com/stripe-cli),
which forwards your Stripe account's test-mode events to the API. It only
starts with the `billing` profile.

1. In `.env`: `BILLING_ENABLED=true` and `STRIPE_SECRET_KEY=sk_test_...`.
2. Start the stack with the profile:

   ```sh
   docker compose --profile billing up --build
   ```

3. The CLI prints a signing secret: find it with
   `docker compose logs stripe | grep whsec_`. Put it in `.env` as
   `STRIPE_WEBHOOK_SECRET`, and restart the API:
   `docker compose --profile billing up -d api`.
4. Send a test event:

   ```sh
   docker compose exec stripe stripe trigger customer.created
   ```

   The API logs `Stripe event evt_... (customer.created) recorded`.

## In production

In the Stripe dashboard, add a webhook endpoint at
`https://<your domain>/billing/webhook` - Caddy sends that one path straight
to the API (`deploy/Caddyfile`) - and put its signing secret in `.env` as
`STRIPE_WEBHOOK_SECRET`, with your live `STRIPE_SECRET_KEY`. Leave
`BILLING_ENABLED=false` until paid plans exist.
