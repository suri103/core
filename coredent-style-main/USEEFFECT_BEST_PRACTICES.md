# React useEffect Best Practices Guide

## 🎯 Quick Reference: When to Use useEffect

This guide helps you decide whether to use `useEffect` or an alternative pattern.

---

## ✅ Valid useEffect Use Cases

### **1. Event Listeners**
```typescript
// ✅ GOOD: External event listener
useEffect(() => {
  const handleResize = () => setWidth(window.innerWidth);
  window.addEventListener('resize', handleResize);
  return () => window.removeEventListener('resize', handleResize);
}, []);
```

### **2. External Library Integration**
```typescript
// ✅ GOOD: Third-party library setup
useEffect(() => {
  const chart = new Chart(canvasRef.current, config);
  return () => chart.destroy();
}, [config]);
```

### **3. WebSocket/Subscription**
```typescript
// ✅ GOOD: WebSocket connection
useEffect(() => {
  const ws = new WebSocket(url);
  ws.onmessage = (event) => setData(JSON.parse(event.data));
  return () => ws.close();
}, [url]);
```

### **4. Analytics/Logging**
```typescript
// ✅ GOOD: Side effect for tracking
useEffect(() => {
  analytics.track('Page Viewed', { page: location.pathname });
}, [location.pathname]);
```

### **5. One-Time Initialization**
```typescript
// ✅ GOOD: Initialize on mount
useEffect(() => {
  checkAuthSession();
}, []);
```

---

## ❌ Invalid useEffect Use Cases

### **1. Derived State**
```typescript
// ❌ BAD: Using useEffect for derived state
const [fullName, setFullName] = useState('');
useEffect(() => {
  setFullName(`${firstName} ${lastName}`);
}, [firstName, lastName]);

// ✅ GOOD: Direct computation
const fullName = `${firstName} ${lastName}`;

// ✅ GOOD: useMemo for expensive computation
const fullName = useMemo(
  () => expensiveComputation(firstName, lastName),
  [firstName, lastName]
);
```

### **2. API Data Fetching**
```typescript
// ❌ BAD: Manual state management
const [data, setData] = useState([]);
const [isLoading, setIsLoading] = useState(true);
const [error, setError] = useState(null);

useEffect(() => {
  setIsLoading(true);
  fetch('/api/data')
    .then(res => res.json())
    .then(setData)
    .catch(setError)
    .finally(() => setIsLoading(false));
}, []);

// ✅ GOOD: React Query
const { data = [], isLoading, error } = useQuery({
  queryKey: ['data'],
  queryFn: () => api.getData(),
});
```

### **3. Prop Synchronization**
```typescript
// ❌ BAD: Syncing props to state
const [value, setValue] = useState(initialValue);
useEffect(() => {
  setValue(initialValue);
}, [initialValue]);

// ✅ GOOD: Direct initialization
const [value, setValue] = useState(initialValue);

// ✅ GOOD: Use key prop to reset component
<Component key={id} initialValue={initialValue} />
```

### **4. Event-Triggered Logic**
```typescript
// ❌ BAD: Using useEffect for event logic
const [count, setCount] = useState(0);
useEffect(() => {
  if (count > 10) {
    alert('Count exceeded!');
  }
}, [count]);

// ✅ GOOD: Handle in event handler
const handleIncrement = () => {
  const newCount = count + 1;
  setCount(newCount);
  if (newCount > 10) {
    alert('Count exceeded!');
  }
};
```

### **5. Resetting State on Prop Change**
```typescript
// ❌ BAD: Using useEffect to reset
const [formData, setFormData] = useState(initialData);
useEffect(() => {
  setFormData(initialData);
}, [userId]);

// ✅ GOOD: Use key prop
<Form key={userId} initialData={initialData} />
```

---

## 🎯 Decision Tree

```
Do you need to perform a side effect?
│
├─ YES → Is it synchronizing with external system?
│   │
│   ├─ YES → Is it an event listener, WebSocket, or library?
│   │   │
│   │   ├─ YES → ✅ Use useEffect
│   │   │
│   │   └─ NO → Is it API data fetching?
│   │       │
│   │       ├─ YES → ✅ Use React Query/SWR
│   │       │
│   │       └─ NO → Is it analytics/logging?
│   │           │
│   │           ├─ YES → ✅ Use useEffect
│   │           │
│   │           └─ NO → ❌ Reconsider approach
│   │
│   └─ NO → Is it computing derived state?
│       │
│       ├─ YES → ✅ Use useMemo or direct computation
│       │
│       └─ NO → Is it responding to user events?
│           │
│           ├─ YES → ✅ Use event handlers
│           │
│           └─ NO → Is it resetting state?
│               │
│               ├─ YES → ✅ Use key prop
│               │
│               └─ NO → ❌ You probably don't need useEffect
│
└─ NO → ❌ Don't use useEffect
```

---

## 📋 Checklist Before Using useEffect

Before writing a `useEffect`, ask yourself:

- [ ] Is this truly a side effect (external system interaction)?
- [ ] Can this be computed directly from props/state?
- [ ] Can this be handled in an event handler?
- [ ] Can this be solved with React Query/SWR?
- [ ] Can this be solved with the `key` prop?
- [ ] Do I need cleanup? (If yes, return cleanup function)
- [ ] Are my dependencies correct?
- [ ] Will this cause infinite loops?

---

## 🔧 Common Patterns

### **Pattern 1: Data Fetching with React Query**
```typescript
// ✅ Recommended pattern
const { data, isLoading, error, refetch } = useQuery({
  queryKey: ['resource', id],
  queryFn: () => api.getResource(id),
  staleTime: 5 * 60 * 1000, // 5 minutes
  enabled: !!id, // Only fetch if id exists
});
```

### **Pattern 2: Debounced Input**
```typescript
// ✅ Valid useEffect for debouncing
useEffect(() => {
  const timer = setTimeout(() => {
    performSearch(searchQuery);
  }, 300);
  return () => clearTimeout(timer);
}, [searchQuery]);
```

### **Pattern 3: Media Query**
```typescript
// ✅ Valid useEffect for external system
useEffect(() => {
  const mql = window.matchMedia('(max-width: 768px)');
  const onChange = () => setIsMobile(mql.matches);
  mql.addEventListener('change', onChange);
  setIsMobile(mql.matches);
  return () => mql.removeEventListener('change', onChange);
}, []);
```

### **Pattern 4: Form Reset on Dialog Open**
```typescript
// ✅ Valid useEffect for UI synchronization
useEffect(() => {
  if (open) {
    form.reset(defaultValues);
  }
}, [open, form, defaultValues]);
```

---

## 🚫 Anti-Patterns to Avoid

### **Anti-Pattern 1: Derived State**
```typescript
// ❌ DON'T DO THIS
const [filteredItems, setFilteredItems] = useState([]);
useEffect(() => {
  setFilteredItems(items.filter(item => item.active));
}, [items]);

// ✅ DO THIS INSTEAD
const filteredItems = items.filter(item => item.active);
```

### **Anti-Pattern 2: Prop Mirroring**
```typescript
// ❌ DON'T DO THIS
const [value, setValue] = useState(props.value);
useEffect(() => {
  setValue(props.value);
}, [props.value]);

// ✅ DO THIS INSTEAD
const [value, setValue] = useState(props.value);
// Or use controlled component pattern
```

### **Anti-Pattern 3: Chaining Effects**
```typescript
// ❌ DON'T DO THIS
useEffect(() => {
  setA(computeA());
}, []);

useEffect(() => {
  setB(computeB(a));
}, [a]);

// ✅ DO THIS INSTEAD
useEffect(() => {
  const newA = computeA();
  setA(newA);
  setB(computeB(newA));
}, []);
```

### **Anti-Pattern 4: Unnecessary Dependencies**
```typescript
// ❌ DON'T DO THIS
useEffect(() => {
  fetchData();
}, [fetchData]); // fetchData recreated every render

// ✅ DO THIS INSTEAD
const fetchData = useCallback(async () => {
  // fetch logic
}, [/* actual dependencies */]);

useEffect(() => {
  fetchData();
}, [fetchData]);
```

---

## 📚 Additional Resources

- [React Query Documentation](https://tanstack.com/query/latest)
- [React useEffect Documentation](https://react.dev/reference/react/useEffect)
- [You Might Not Need an Effect](https://react.dev/learn/you-might-not-need-an-effect)
- [Separating Events from Effects](https://react.dev/learn/separating-events-from-effects)

---

## 🎓 Team Guidelines

### **Code Review Checklist**
When reviewing code with `useEffect`:
- [ ] Is this useEffect necessary?
- [ ] Could this be React Query instead?
- [ ] Could this be derived state?
- [ ] Could this be an event handler?
- [ ] Are dependencies correct?
- [ ] Is cleanup handled properly?
- [ ] Is there a comment explaining why?

### **Adding New useEffect**
When adding a new `useEffect`:
1. Check this guide first
2. Consider alternatives
3. Add a comment explaining why it's necessary
4. Ensure proper cleanup
5. Test for memory leaks
6. Document in code review

### **Comment Format for Necessary useEffect**
```typescript
// effect:audited — [Brief explanation of why this is necessary]
useEffect(() => {
  // implementation
}, [dependencies]);
```

---

**Last Updated:** March 20, 2026  
**Maintained By:** Frontend Team  
**Questions?** Ask in #frontend-architecture
