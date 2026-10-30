// ============================================
// CoreDent PMS - Key-Case Normalization
// ============================================
// The FastAPI backend serializes Pydantic models with snake_case field names
// on the wire (first_name, date_of_birth, ...). The React layer uses one
// stable camelCase shape (firstName, dateOfBirth, ...) for every domain,
// matching the documented API contract in API.md.
//
// These helpers are the single boundary that reconciles the two dialects:
//   - camelToSnake(): applied to request bodies + query params (frontend -> API)
//   - snakeToCamel(): applied to JSON response bodies (API -> frontend)
//
// Both transforms are idempotent for keys that are already in the target
// dialect (a key with no underscores is never changed by camelToSnake, and
// a key without uppercase is never changed by snakeToCamel), so callers can
// run them unconditionally without corrupting data.

type PlainObject = Record<string, unknown>;

function isPlainObject(value: unknown): value is PlainObject {
  return (
    value !== null &&
    typeof value === 'object' &&
    !Array.isArray(value) &&
    !(value instanceof Date) &&
    !(value instanceof FormData) &&
    !(value instanceof File) &&
    !(value instanceof Blob)
  );
}

/** foo_bar / FooBar -> fooBar. Leaves dialect-free keys untouched. */
export function snakeToCamelKey(key: string): string {
  return key.replace(/_([a-z0-9])/g, (_, ch: string) => ch.toUpperCase());
}

/** fooBar -> foo_bar. Leaves dialect-free keys untouched. */
export function camelToSnakeKey(key: string): string {
  return key.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toLowerCase();
}

/** Recursively converts every key in an object/array tree from snake_case to camelCase. */
export function snakeToCamel<T>(value: T): T {
  if (Array.isArray(value)) {
    return value.map((item) => snakeToCamel(item)) as unknown as T;
  }
  if (isPlainObject(value)) {
    const out: PlainObject = {};
    for (const [key, val] of Object.entries(value)) {
      out[snakeToCamelKey(key)] = snakeToCamel(val);
    }
    return out as unknown as T;
  }
  return value;
}

/** Recursively converts every key in an object/array tree from camelCase to snake_case. */
export function camelToSnake<T>(value: T): T {
  if (Array.isArray(value)) {
    return value.map((item) => camelToSnake(item)) as unknown as T;
  }
  if (isPlainObject(value)) {
    const out: PlainObject = {};
    for (const [key, val] of Object.entries(value)) {
      out[camelToSnakeKey(key)] = camelToSnake(val);
    }
    return out as unknown as T;
  }
  return value;
}