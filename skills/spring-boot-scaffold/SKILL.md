---
name: spring-boot-scaffold
description: Generate complete Spring Boot project scaffolding including REST controllers, services, repositories, DTOs, mappers, exception handlers, and configuration. Use this skill whenever the user wants to bootstrap a Spring Boot feature, create a new REST endpoint, generate a CRUD layer, scaffold a new module, or says things like "create a Spring Boot API for X", "generate the boilerplate for X entity", "I need a REST layer for X", "scaffold a service for X". Always use this skill when any Spring Boot or Java backend generation is needed — don't write it from scratch without consulting this skill.
---

# Spring Boot Scaffold Skill

Generate production-ready Spring Boot boilerplate following best practices: layered architecture, proper exception handling, validation, and clean DTO separation.

## Architecture Layers to Generate

Always generate the full vertical slice unless the user specifies otherwise:

```
Controller → Service (interface + impl) → Repository → Entity
                    ↓
              DTO (Request/Response) + Mapper + Exception Handler
```

## Generation Rules

### Entity
- Annotate with `@Entity`, `@Table(name = "...")`
- Use `@Id` + `@GeneratedValue(strategy = GenerationType.IDENTITY)`
- Add `@CreationTimestamp` / `@UpdateTimestamp` for audit fields
- Use Lombok: `@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder`
- Prefer `LocalDateTime` over `Date`

### Repository
- Extend `JpaRepository<Entity, Long>`
- Add custom query methods using Spring Data naming conventions
- Use `@Query` with JPQL (not native SQL) for complex queries
- Always add `Optional<Entity> findByXxx(...)` for unique lookups

### DTO (Request/Response)
- **Separate** Request and Response DTOs — never reuse the Entity as DTO
- Request DTOs: add Bean Validation (`@NotNull`, `@NotBlank`, `@Size`, `@Email`, etc.)
- Response DTOs: include only fields safe to expose
- Use Lombok `@Data` for DTOs

### Mapper
- Use **MapStruct** by default: `@Mapper(componentModel = "spring")`
- Define `toEntity(RequestDto)`, `toResponse(Entity)`, `toResponseList(List<Entity>)`
- If MapStruct not available, generate a static `EntityMapper` utility class

### Service
- Always create an **interface** + **implementation** pair
- Annotate impl with `@Service`, `@Transactional` at class level
- Override `@Transactional(readOnly = true)` on read methods
- Throw specific custom exceptions (never generic `RuntimeException`)
- Use `repository.findById(id).orElseThrow(() -> new ResourceNotFoundException(...))`

### Controller
- Annotate with `@RestController`, `@RequestMapping("/api/v1/resource")`
- Use `@Valid` on `@RequestBody` parameters
- Return `ResponseEntity<T>` with explicit HTTP status:
  - GET list → `200 OK`
  - GET by id → `200 OK`
  - POST → `201 Created`
  - PUT/PATCH → `200 OK`
  - DELETE → `204 No Content`
- Add `@Tag(name = "...")` for Swagger/OpenAPI documentation

### Exception Handling
Always generate a `@RestControllerAdvice` with:
- `ResourceNotFoundException` → `404 Not Found`
- `ValidationException` / `MethodArgumentNotValidException` → `400 Bad Request`
- `DataIntegrityViolationException` → `409 Conflict`
- Generic `Exception` fallback → `500 Internal Server Error`
- Standard error response body: `{ timestamp, status, error, message, path }`

## Output Format

Generate files in this order:
1. Entity class
2. Repository interface
3. Request DTO + Response DTO
4. Mapper interface
5. Service interface + ServiceImpl
6. Controller
7. Custom exceptions
8. GlobalExceptionHandler

Add a comment header to each file:
```java
// === [FileName].java ===
// Layer: [Entity|Repository|DTO|Service|Controller|Exception]
```

## Example Trigger

User: *"Create a Spring Boot CRUD for a Product entity with name, price, and category"*

→ Generate all 8 file types listed above for the `Product` domain.

## Dependencies to Mention

If the user hasn't set up the project yet, remind them to include:
```xml
spring-boot-starter-web
spring-boot-starter-data-jpa
spring-boot-starter-validation
lombok
mapstruct
springdoc-openapi-starter-webmvc-ui
```
