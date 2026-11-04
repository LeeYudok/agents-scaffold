---
paths:
  - "**/*.php"
  - "app/**/*.php"
  - "routes/**/*.php"
  - "config/**/*.php"
  - "database/**/*.php"
  - "tests/**/*.php"
  - "resources/views/**/*.blade.php"
  - "composer.json"
---

# PHP · Laravel Rules

## Runtime & package management
- Pin the PHP version with the `require.php` constraint in `composer.json`; keep it in sync with the CI and production runtimes.
- Change dependencies only through `composer require`/`composer update <package>` and **commit `composer.lock`**.
- Run tooling through the project-local binaries (`vendor/bin/pint`, `vendor/bin/phpunit`, `php artisan`) — never a global install.

## Code conventions
- Use `pint` (Laravel preset) as the single style source. Run `vendor/bin/pint` before committing.
- Declare `declare(strict_types=1);` in every file, with parameter and return types.
- Keep controllers thin: validate requests with Form Requests and move domain logic to `app/Actions/`/`app/Services/`.
- Read settings through `config()`. Call `env()` only inside `config/*.php` — after `config:cache`, any other `env()` call returns `null`.
- Fix N+1 queries with `with()`/`load()`. Enable `Model::preventLazyLoading()` locally.
- Make queued jobs and event listeners idempotent — a retry that runs twice must give the same result.

## Testing
- PHPUnit (or Pest) — `tests/Feature` for HTTP/DB boundaries, `tests/Unit` for pure logic.
- Isolate DB-backed tests with `RefreshDatabase` (or `DatabaseTransactions`) and build test data with model factories.
- Stub external HTTP, mail and queues with `Http::fake()`/`Mail::fake()`/`Queue::fake()`.
- Every feature or bug fix ships with at least one test (P1).

## Migrations & DB
- Keep migrations reversible by filling in `down()`. Never edit a migration that has already shipped — add a new one.
- Split adding a `NOT NULL` column to a production table into: add as nullable → backfill → add the constraint.
- Bulk data changes belong in a chunked (`chunkById`) command, not in a migration.

## Security
- Secrets live only in `.env` (never committed) and production environment variables. **Never commit** `APP_KEY`, `auth.json` (Composer credentials) or `storage/oauth-*.key` (Passport).
- SQL goes through Eloquent/query-builder bindings only. Never interpolate request values into `DB::raw`/`whereRaw`/`orderByRaw`.
- Whitelist mass assignment with `$fillable`. No `$guarded = []`, no `forceFill($request->all())`.
- Blade output uses `{{ }}` (escaped). If you use `{!! !!}`, justify the input's origin in a comment.
- `APP_DEBUG=false` in production. Put state-changing routes behind the `auth` (or `auth:sanctum`) middleware and CSRF protection.

## P0
- Never hardcode secrets — never stage `.env`, `auth.json` or `storage/oauth-*.key`
- Never concatenate strings into SQL — bound parameters only
- Commit only after `composer validate` + `vendor/bin/pint --test` pass

## P1
- Commit `composer.lock` and migrations together with the change
- Every feature or bug fix ships with at least one test
- Use only request input validated by a Form Request (or `$request->validate()`)
