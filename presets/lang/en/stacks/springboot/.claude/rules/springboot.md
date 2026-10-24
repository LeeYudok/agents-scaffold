---
paths:
  - "src/main/java/**/*.java"
  - "src/test/java/**/*.java"
---

# Spring Boot / Backend Rules

## P0

- Never hardcode secrets (DB passwords, API keys) in `application.yml` or source → env vars or external config
- Never concatenate user input into JPA queries — bind parameters only
- `./gradlew compileJava` (or `mvn -q compile`) must pass before commit
- No new unauthenticated endpoints — they go behind Spring Security config

- **Java {{JAVA_VERSION}} (= Java 8) → Spring Boot 2.7.x line** (3.x requires Java 17+, so it cannot be used).
  2.7 is OSS EOL (2023-06, no security patches) and commercial support ends in late 2026 — a deliberate legacy choice driven by the Java 8 constraint; handle vulnerabilities at the dependency level.
- Build tool: **Gradle** (`./gradlew`).
- Layered architecture: `controller` → `service` → `repository`. No business logic in controllers.
- Dependency injection via **constructor injection** (no field injection), lombok `@RequiredArgsConstructor`.
- Validate request DTOs with Bean Validation (`@Valid`, `@NotNull`, etc.).
- No hardcoding secrets/DB passwords in `application.yml` → use environment variables/`.env`.
- Do not expose entities directly in responses → convert to DTOs, excluding password/hash/token fields.
