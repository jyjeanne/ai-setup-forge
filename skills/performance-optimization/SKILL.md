---
name: performance-optimization
description: Identify and fix performance issues in Java/Spring Boot applications including slow queries, memory leaks, thread contention, caching strategies, and JVM tuning. Use this skill whenever the user has a slow application, performance issue, wants to add caching, needs to optimize queries, profile memory usage, or says things like "my API is slow", "optimize this", "add caching", "reduce response time", "memory leak", "high CPU usage", "this query is taking too long", "how do I cache this". Always use this skill for any Java/Spring Boot performance optimization task.
---

# Java Performance Optimization Skill

Diagnose and resolve performance bottlenecks in Spring Boot applications across all layers: database, application, JVM, and infrastructure.

## Performance Investigation Framework

When given a performance issue, investigate in this order:

```
1. Database (80% of bottlenecks are here)
   → Slow queries, N+1, missing indexes, full table scans

2. Application Layer
   → Unnecessary computations, poor data structures, synchronous blocking calls

3. Caching
   → Missing cache on hot read paths, cache invalidation issues

4. Thread Pool / Concurrency
   → Thread starvation, blocking I/O on request threads, lock contention

5. JVM / Memory
   → GC pressure, memory leaks, heap sizing
```

---

## Database Performance

### Identify Slow Queries

```yaml
# Enable slow query logging
logging:
  level:
    org.hibernate.SQL: DEBUG
spring:
  jpa:
    properties:
      hibernate:
        generate_statistics: true
        session.events.log.LOG_QUERIES_SLOWER_THAN_MS: 100
```

Check with Spring Boot Actuator:
```
GET /actuator/metrics/hibernate.query.executions
GET /actuator/metrics/hibernate.query.executions.max
```

### Index Strategy

```sql
-- Analyze query plans
EXPLAIN ANALYZE SELECT * FROM orders WHERE customer_id = 42 AND status = 'PENDING';

-- Common indexes to add
CREATE INDEX idx_orders_customer_status ON orders(customer_id, status);  -- composite
CREATE INDEX idx_products_name_gin ON products USING gin(to_tsvector('english', name));  -- full-text
CREATE INDEX idx_orders_created_at ON orders(created_at DESC);  -- sort optimization

-- Partial index (only index relevant subset)
CREATE INDEX idx_active_users ON users(email) WHERE active = true;
```

### Query Optimization Patterns

**Use projections instead of full entity loading**
```java
// ❌ Loads all 30 columns for a list view
List<User> findAll();

// ✅ Load only what the UI needs
public interface UserSummary {
    Long getId();
    String getName();
    String getEmail();
}

List<UserSummary> findAllProjectedBy();

// ✅ DTO projection via JPQL
@Query("SELECT new com.example.dto.UserSummaryDto(u.id, u.name, u.email) FROM User u")
List<UserSummaryDto> findAllSummaries();
```

**Batch inserts / updates**
```java
// Enable batch inserts
spring.jpa.properties.hibernate.jdbc.batch_size=50
spring.jpa.properties.hibernate.order_inserts=true
spring.jpa.properties.hibernate.order_updates=true

// In repository — use saveAll() not repeated save()
userRepository.saveAll(users);  // ✅ batched
users.forEach(userRepository::save);  // ❌ N queries
```

---

## Caching Strategy

### Spring Cache Setup

```xml
<!-- pom.xml -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-cache</artifactId>
</dependency>
<!-- For production: use Redis -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-data-redis</artifactId>
</dependency>
```

```java
@SpringBootApplication
@EnableCaching
public class Application { ... }
```

### Caching Annotations

```java
// Cache on first call, return cached on subsequent calls
@Cacheable(value = "products", key = "#id")
public ProductResponse findById(Long id) { ... }

// Cache with condition
@Cacheable(value = "products", key = "#filter.hashCode()", 
           condition = "#filter.size() < 100")
public List<ProductResponse> findByFilter(ProductFilter filter) { ... }

// Evict cache on update
@CacheEvict(value = "products", key = "#id")
public ProductResponse update(Long id, UpdateRequest request) { ... }

// Evict entire cache
@CacheEvict(value = "products", allEntries = true)
public void refreshAllProducts() { ... }

// Update cache after write
@CachePut(value = "products", key = "#result.id")
public ProductResponse create(CreateRequest request) { ... }
```

### Redis Configuration for Production

```yaml
spring:
  cache:
    type: redis
    redis:
      time-to-live: 600000  # 10 minutes in ms
      cache-null-values: false
  redis:
    host: localhost
    port: 6379
```

```java
@Bean
public RedisCacheConfiguration cacheConfiguration() {
    return RedisCacheConfiguration.defaultCacheConfig()
        .entryTtl(Duration.ofMinutes(10))
        .disableCachingNullValues()
        .serializeValuesWith(RedisSerializationContext.SerializationPair
            .fromSerializer(new GenericJackson2JsonRedisSerializer()));
}
```

### What to Cache

| Cache | TTL | Eviction Trigger |
|-------|-----|-----------------|
| Reference data (categories, config) | 1 hour | Manual or scheduled |
| User profile | 15 min | On user update |
| Product catalog | 10 min | On product update |
| Search results | 5 min | Time-based only |
| Authentication tokens | Token expiry | On logout |

**Do NOT cache**: user-specific financial data, frequently mutating entities, large collections (> 1000 items)

---

## Async Processing

For operations that don't need to block the HTTP request:

```java
@Configuration
@EnableAsync
public class AsyncConfig {
    @Bean(name = "taskExecutor")
    public Executor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(5);
        executor.setMaxPoolSize(20);
        executor.setQueueCapacity(100);
        executor.setThreadNamePrefix("async-");
        executor.initialize();
        return executor;
    }
}

@Service
public class NotificationService {

    // Runs in a separate thread pool — doesn't block the caller
    @Async("taskExecutor")
    public CompletableFuture<Void> sendWelcomeEmail(String email) {
        // Heavy email sending logic
        return CompletableFuture.completedFuture(null);
    }
}
```

---

## Connection Pool Tuning (HikariCP)

```yaml
spring:
  datasource:
    hikari:
      maximum-pool-size: 20       # Rule: (cores * 2) + effective_spindle_count
      minimum-idle: 5
      connection-timeout: 30000   # 30s max wait for connection
      idle-timeout: 600000        # 10min — release unused connections
      max-lifetime: 1800000       # 30min — recycle connections
      leak-detection-threshold: 60000  # Warn if connection held > 60s
```

---

## Memory & GC Optimization

### JVM Flags for Spring Boot in Production

```bash
java \
  -Xms512m -Xmx2g \
  -XX:+UseG1GC \
  -XX:MaxGCPauseMillis=200 \
  -XX:+HeapDumpOnOutOfMemoryError \
  -XX:HeapDumpPath=/var/log/heapdump.hprof \
  -jar app.jar
```

### Common Memory Leak Patterns in Spring Boot

```java
// ❌ Static collection that never shrinks (classic leak)
private static final Map<Long, UserSession> activeSessions = new HashMap<>();

// ✅ Use Caffeine/Guava cache with eviction
@Bean
public Cache<Long, UserSession> sessionCache() {
    return Caffeine.newBuilder()
        .maximumSize(10_000)
        .expireAfterAccess(30, TimeUnit.MINUTES)
        .build();
}
```

---

## Performance Profiling Checklist

Before optimizing, measure:

- [ ] Identify the slowest endpoint (use Actuator `/actuator/metrics` or APM tool)
- [ ] Check Hibernate statistics for N+1 patterns
- [ ] Run `EXPLAIN ANALYZE` on the top 5 slowest SQL queries
- [ ] Check HikariCP pool metrics (pool exhaustion?)
- [ ] Check GC pause frequency and duration
- [ ] Profile with async-profiler or JFR for CPU-bound issues

**Golden Rule**: Measure first, optimize second. Never optimize without data.
