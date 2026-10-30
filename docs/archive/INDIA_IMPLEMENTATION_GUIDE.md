# 🇮🇳 India Implementation Guide

## Features to Implement for Indian Market

---

## 1. ✅ Hindi i18n - COMPLETED

**Status:** Implemented and pushed
- Hindi translations for 100+ UI strings
- Navigation, billing, patient, appointment sections
- Language selector in Settings shows Hindi (हिंदी)

**Files modified:**
- `coredent-style-main/src/lib/i18n.ts`

---

## 2. GST Compliance - Implementation Steps

### Backend Changes Required

#### A. Add GST fields to Invoice model
```sql
-- Migration to add GST fields to billing table
ALTER TABLE invoices 
ADD COLUMN gstin VARCHAR(15),
ADD COLUMN gst_rate DECIMAL(5,2) DEFAULT 18.00,
ADD COLUMN gst_amount DECIMAL(10,2) DEFAULT 0.00,
ADD COLUMN cgst_amount DECIMAL(10,2) DEFAULT 0.00,
ADD COLUMN sgst_amount DECIMAL(10,2) DEFAULT 0.00,
ADD COLUMN igst_amount DECIMAL(10,2) DEFAULT 0.00;
```

#### B. Add GST calculation endpoint
Create file: `coredent-api/app/api/v1/endpoints/gst.py`

```python
@router.post("/calculate")
async def calculate_gst(amount: float, gst_rate: float, inter_state: bool):
    """Calculate GST for Indian invoices"""
    gst_amount = (amount * gst_rate) / 100
    if inter_state:
        # IGST (Central + State combined)
        igst = gst_amount
        return {"cgst": 0, "sgst": 0, "igst": igst, "total": amount + igst}
    else:
        # CGST + SGST split
        cgst = gst_amount / 2
        sgst = gst_amount / 2
        return {"cgst": cgst, "sgst": sgst, "igst": 0, "total": amount + cgst + sgst}
```

#### C. Add GST to billing schema
Add to `coredent-api/app/schemas/billing.py`:
```python
gstin: Optional[str] = Field(None, max_length=15)
gst_rate: float = 18.0  # Default 18%
gst_amount: float = 0.0
cgst_amount: float = 0.0
sgst_amount: float = 0.0
igst_amount: float = 0.0
```

### Frontend Changes Required

#### A. Add GST fields to invoice form
In `coredent-style-main/src/pages/Billing.tsx`:
- Add GSTIN input field
- Add GST rate selector (5%, 12%, 18%, 28%)
- Auto-calculate CGST/SGST/IGST
- Show CGST + SGST or IGST based on state

#### B. GST-compliant invoice template
Add to invoice PDF/receipt:
```
CoreDent Dental Clinic
GSTIN: 27AABCU9603R1ZM
State: Maharashtra

Item          | Amount  | GST Rate | CGST | SGST | Total
Cleaning      | ₹1000   | 18%      | ₹90  | ₹90  | ₹1180
```

---

## 3. ABHA Integration - Implementation Steps

### Backend Changes Required

#### A. Add ABHA field to patient model
```sql
ALTER TABLE patients 
ADD COLUMN abha_number VARCHAR(14),
ADD COLUMN abha_verified BOOLEAN DEFAULT FALSE,
ADD COLUMN abha_verified_at TIMESTAMP;
```

#### B. ABHA verification API endpoint
Create file: `coredent-api/app/api/v1/endpoints/abha.py`

```python
@router.post("/verify")
async def verify_abha(abha_number: str):
    """Verify ABHA number with ABDM API"""
    # ABDM API integration
    # Returns patient details if valid
    pass

@router.post("/link")
async def link_abha(patient_id: UUID, abha_number: str):
    """Link ABHA to patient profile"""
    pass
```

### Frontend Changes Required

#### A. Add ABHA field to patient registration
In `coredent-style-main/src/components/patients/`:
- Add ABHA number input in patient form
- Add verify button with ABDM API call
- Show verified badge

---

## 4. Offline Mode - Implementation Steps

### Frontend Changes Required

#### A. Create service worker
Create file: `coredent-style-main/public/sw.js`:
```javascript
const CACHE_NAME = 'coredent-v1';
const urlsToCache = [
  '/',
  '/index.html',
  '/static/js/bundle.js',
  '/static/css/main.css',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});
```

#### B. Add IndexedDB for offline data
Create file: `coredent-style-main/src/lib/offline.ts`:
```typescript
// Store patient data, appointments offline
// Sync when connection restored
```

---

## 5. Mobile Responsive - Implementation Steps

### Priority fixes:
- [ ] Fix table overflow on mobile screens
- [ ] Add swipe gestures for navigation
- [ ] Optimize touch targets (min 44px)
- [ ] Add PWA manifest for "Add to Home Screen"
- [ ] Optimize images for mobile bandwidth

---

## Implementation Priority Order

1. ✅ **Hindi i18n** - Done
2. 🥇 **GST Compliance** - Critical for Indian launch
3. 🥈 **Mobile Responsive** - Essential for Indian users
4. 🥉 **Offline Mode** - Nice to have
5. 📋 **ABHA Integration** - Future enhancement

---

## Estimated Timeline

| Feature | Effort | Value |
|---------|--------|-------|
| GST Compliance | 2-3 days | High (legal requirement) |
| Mobile Responsive | 1-2 days | High (user experience) |
| Offline Mode | 3-4 days | Medium |
| ABHA Integration | 1 week | Medium (niche) |