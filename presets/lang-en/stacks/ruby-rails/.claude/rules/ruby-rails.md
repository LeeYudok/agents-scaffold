---
paths:
  - "**/*.rb"
  - "app/**/*.rb"
  - "lib/**/*.rb"
  - "config/**/*.rb"
  - "db/**/*.rb"
  - "spec/**/*.rb"
  - "app/**/*.erb"
  - "Gemfile"
---

# Ruby on Rails Rules

## Runtime & package management
- Pin the Ruby version in `.ruby-version`; keep it in sync with the `ruby` directive in `Gemfile`.
- Update dependencies through `bundle add`/`bundle update` and **commit `Gemfile.lock`**.
- Run tooling through `bundle exec` (`bundle exec rspec`, `bundle exec rubocop`) — never a global gem.

## Code conventions
- `rubocop` (+ `rubocop-rails`, `rubocop-rspec`) is the single style source. Run `bundle exec rubocop -A` before committing.
- Keep controllers thin: HTTP translation and authorization only. Domain logic belongs in models or `app/services/`.
- No business logic or external I/O in callbacks (`before_save` and friends) — extract a service object.
- Keep fat queries in the model as scopes / `ActiveRecord::Relation`. Never query from a view.
- Resolve N+1 with `includes`/`preload`. The `bullet` gem is recommended.

## Testing
- RSpec by default (`spec/`). Prefer model and request specs; reserve system specs for core flows.
- Prefer `factory_bot` over fixtures. Keep transactional rollback enabled in `spec/rails_helper.rb`.
- Every feature and bug fix ships with at least one spec (P1).

## Migrations & DB
- Migrations must be reversible (use explicit `up`/`down` when `change` cannot express it).
- Split "add `NOT NULL` + default" from the backfill on production tables; roll it out in steps.
- On large tables add indexes with `algorithm: :concurrently` (PostgreSQL, together with `disable_ddl_transaction!`).
- Commit `schema.rb` (or `structure.sql`) in the same commit as the migration.

## Security
- Secrets live in Rails credentials (`config/credentials.yml.enc`) or environment variables. **Never commit** `config/master.key` or `config/credentials/*.key`.
- Bind SQL through placeholders (`where("id = ?", id)`). No string interpolation.
- Whitelist mass assignment with strong parameters. `permit!` is forbidden.
- When using `raw`/`html_safe` in ERB, leave a comment justifying the input's origin.

## P0
- Never hardcode secrets — never stage `config/master.key`, `config/credentials/*.key`, or `.env`
- Never interpolate strings into SQL — bound parameters only
- Commit only with `bundle exec rubocop` clean

## P1
- Commit `Gemfile.lock` and `schema.rb`/`structure.sql` alongside the change
- Ship at least one spec with every feature and bug fix
- Controllers accept parameters only through a strong-parameters whitelist
