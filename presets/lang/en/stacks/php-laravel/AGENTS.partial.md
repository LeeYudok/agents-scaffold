
**php-laravel**

- Never hardcode secrets — read values from `.env` only through `config()`, and never stage `.env`, `auth.json` or `storage/oauth-*.key`
- Never concatenate strings into SQL — Eloquent/query-builder bindings only (no input interpolated into `DB::raw`/`whereRaw`)
- Commit only after `composer validate` + `vendor/bin/pint --test` pass
