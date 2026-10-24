
**ruby-rails**

- Never hardcode secrets — never stage `config/master.key` or `.env`
- Never interpolate strings into SQL — bound parameters only
- Commit only with `bundle exec rubocop` clean
