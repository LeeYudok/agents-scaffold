
**springboot**

- Never hardcode secrets (DB passwords, API keys) in `application.yml` or source → env vars or external config
- Never concatenate user input into JPA queries — bind parameters only
- `./gradlew compileJava` (or `mvn -q compile`) must pass before commit
- No new unauthenticated endpoints — they go behind Spring Security config
