# Dental Insurance EDI Clearinghouse Guide

**Date:** March 31, 2026  
**Purpose:** Complete guide to getting insurance EDI connectivity for CoreDent PMS

---

## What is a Dental Clearinghouse?

A **dental clearinghouse** is a middleman service that translates your software's data into standardized insurance formats (X12 837D for claims, X12 276/277 for eligibility, X12 835 for payments) and routes them to 1,000+ dental insurance carriers (Delta Dental, Cigna, MetLife, Aetna, Guardian, etc.).

Think of it as a "universal adapter" — instead of building 1,000+ separate integrations with each insurance company, you integrate with ONE clearinghouse and they handle the rest.

---

## Top Clearinghouse Options for Dental PMS

### 1. DentalXChange (DentalXChange API) ⭐ RECOMMENDED
- **Website:** https://www.dentalxchange.com
- **API:** https://api.dentalxchange.com
- **Coverage:** 1,500+ dental insurance carriers
- **Setup Fee:** $0-1,000 (negotiable)
- **Monthly Fee:** $100-250/month
- **Per-Claim Fee:** $0.10-0.25 per claim
- **Support:** RESTful API, webhooks
- **Onboarding Time:** 2-4 weeks
- **Contact:** api-sales@dentalxchange.com | (888) 474-6220
- **Best For:** New PMS vendors, startup-friendly

**Services Offered:**
- Eligibility checking (real-time)
- Claims submission
- Claim status inquiry
- Remittance/EOB processing
- Attachments (X-rays, photos)
- Pre-determination

### 2. ChangeEDC (formerly DentalBridge)
- **Website:** https://www.changeedc.com
- **Coverage:** 2,500+ carriers
- **Setup Fee:** $500-2,000
- **Monthly Fee:** $150-300/month
- **Per-Claim Fee:** $0.15-0.30 per claim
- **Onboarding Time:** 3-6 weeks
- **Contact:** partnerships@changeedc.com
- **Best For:** Larger practices, multi-specialty

### 3. Dentrix EDI Solutions
- **Website:** https://www.dentrix.com
- **Note:** Primarily for existing Dentrix partners — harder for new vendors
- **Setup Fee:** $2,500-5,000
- **Monthly Fee:** $200-500/month
- **Not Recommended** for startups (requires partnership approval)

### 4. X12 Direct (via Availity or Waystar)
- **Website:** https://www.availity.com or https://waystar.com
- **Coverage:** Comprehensive (medical + dental)
- **Setup Fee:** $1,000-5,000
- **Monthly Fee:** $200-500/month
- **Onboarding Time:** 4-8 weeks
- **Best For:** Practices that submit medical-dental crossover claims

### 5. Open Dental EDI (Open Dental Partners) ⭐ ALTERNATIVE
- **Website:** https://www.opendental.com
- **Note:** They offer their clearinghouse service to other PMS vendors
- **Setup Fee:** $500-1,000
- **Monthly Fee:** $99-199/month
- **Contact:** edi@opendental.com
- **Best For:** Budget-conscious startups

---

## Cost Comparison Summary

| Clearinghouse | Setup | Monthly | Per-Claim | Total Year 1 | Best For |
|---------------|-------|---------|-----------|-------------|----------|
| **DentalXChange** | $0-1,000 | $100-250 | $0.10-0.25 | **$1,200-4,000** | Best overall |
| ChangeEDC | $500-2,000 | $150-300 | $0.15-0.30 | $2,300-6,600 | Multi-specialty |
| Open Dental EDI | $500-1,000 | $99-199 | $0.12-0.20 | $1,700-3,400 | Budget option |
| Availity/Waystar | $1,000-5,000 | $200-500 | $0.20-0.35 | $3,400-11,000 | Medical-dental |

### Your Estimated Monthly Cost (Based on Practice Size):

| Scenario | Claims/Month | Clearinghouse Fee | Per-Claim Cost | Total Monthly |
|----------|-------------|-------------------|----------------|--------------|
| 10 small practices | 100 | $150 | $0.15 × 100 = $15 | **$165/mo** |
| 50 medium practices | 500 | $200 | $0.12 × 500 = $60 | **$260/mo** |
| 200 practices | 2,000 | $250 | $0.10 × 2,000 = $200 | **$450/mo** |
| 500 practices | 5,000 | $300 | $0.08 × 5,000 = $400 | **$700/mo** |

---

## How to Get Started (Step-by-Step)

### Step 1: Contact Clearinghouses (Week 1)
**Email Template:**
```
Subject: Dental PMS Vendor - EDI Integration Inquiry

Hello [Clearinghouse Name] Team,

I am the founder of CoreDent PMS, a modern cloud-based dental practice 
management software. We are looking to integrate dental insurance EDI 
services including:
- Real-time eligibility verification (X12 270/271)
- Electronic claims submission (X12 837D)
- Claim status inquiry (X12 276/277)
- Electronic remittance advice (X12 835)

We are targeting small to medium dental practices (1-5 locations) 
and expect to start with 50-100 practices in Year 1.

Please provide:
1. API documentation
2. Pricing for a new PMS vendor
3. Onboarding timeline
4. Sandbox/testing environment access
5. Required certifications/credentials

Our company details:
- Company: CoreDent PMS
- Website: [your-website]
- Contact: [your-email]
- Expected claims volume: 500-2,000/month Year 1

Thank you,
[Your Name]
```

### Step 2: Get Credentials & Sandbox Access (Week 1-2)
- Clearinghouse provides API keys
- Testing environment with sample data
- Documentation for X12 EDI formats
- Integration guides

### Step 3: Build API Integration (Weeks 2-4)
**What You Need to Build:**

#### A. Eligibility Check API
```python
# Example: Check patient insurance coverage
POST https://api.dentalxchange.com/v1/eligibility
{
    "subscriber_id": "PAT-123456",
    "subscriber_name": "John Doe",
    "subscriber_dob": "1985-03-15",
    "payer_id": "DENTDELTA001",
    "group_number": "GRP12345"
}

# Response:
{
    "status": "active",
    "coverage": {
        "preventive": "100%",
        "basic": "80%",
        "major": "50%",
        "orthodontia": "$1,500 lifetime max",
        "annual_maximum": "$1,500",
        "deductible_remaining": "$50"
    }
}
```

#### B. Claims Submission API
```python
# Example: Submit dental claim
POST https://api.dentalxchange.com/v1/claims
{
    "claim_type": "dental",
    "patient": {...},
    "subscriber": {...},
    "provider": {...},
    "procedures": [
        {
            "code": "D0120",  # Periodic oral evaluation
            "tooth_number": "",
            "surface": "",
            "fee": 75.00,
            "date_of_service": "2026-03-31"
        },
        {
            "code": "D1110",  # Adult prophylaxis
            "tooth_number": "",
            "surface": "",
            "fee": 125.00,
            "date_of_service": "2026-03-31"
        },
        {
            "code": "D2391",  # Composite resin - posterior
            "tooth_number": "30",
            "surface": "MOD",
            "fee": 350.00,
            "date_of_service": "2026-03-31"
        }
    ]
}

# Response:
{
    "claim_id": "CLM-2026-001234",
    "status": "submitted",
    "estimated_payment_date": "2026-04-14"
}
```

#### C. Claim Status Check API
```python
# Example: Check if claim was processed
GET https://api.dentalxchange.com/v1/claims/CLM-2026-001234/status

# Response:
{
    "claim_id": "CLM-2026-001234",
    "status": "paid",
    "paid_amount": 412.50,
    "patient_responsibility": 137.50,
    "adjustment_amount": 0.00,
    "payment_date": "2026-04-10"
}
```

#### D. Remittance/Webhook for Payments
```python
# Webhook: Insurance company paid a claim
POST https://your-api.com/webhooks/edc-remittance
{
    "event": "claim_payment",
    "claim_id": "CLM-2026-001234",
    "payment_amount": 412.50,
    "patient_responsibility": 137.50,
    "line_items": [...],
    "adjustments": [...]
}
```

### Step 4: Testing (Weeks 4-5)
- Submit test claims to sandbox
- Verify eligibility responses
- Test claim status tracking
- Test payment posting (EOB)
- Edge cases: denied claims, partial payments, coordination of benefits

### Step 5: Certification (Weeks 5-6)
- Clearinghouse reviews your integration
- Passes validation tests
- Signs partnership agreement
- Receives production credentials

### Step 6: Beta Launch (Week 6-8)
- Onboard 3-5 beta practices
- Monitor claim flow
- Fix any production issues
- Get clearinghouse approval for scaling

---

## Technical Requirements

### What Your System Already Has:
- ✅ Insurance database models
- ✅ Insurance API endpoints
- ✅ Insurance frontend pages
- ✅ EDI endpoint structure
- ✅ Patient demographics system
- ✅ Treatment/procedure system
- ✅ Billing/payments system

### What's Missing (To Build):

| Component | Effort | Description |
|-----------|--------|-------------|
| **Clearinghouse API Client** | 1 week | HTTP client for clearinghouse REST APIs |
| **Eligibility Module** | 1 week | Check insurance coverage before appointments |
| **Claims Builder** | 1-2 weeks | Convert procedures to X12 837D claims |
| **Claim Status Tracker** | 0.5 week | Automated claim status checking |
| **EOB/Remittance Processor** | 1 week | Parse payments, auto-post to accounts |
| **Frontend Integration** | 1-2 weeks | Insurance eligibility UI, claims dashboard |
| **Testing & Certification** | 2 weeks | Sandbox testing, clearinghouse review |
| **TOTAL** | **6-8 weeks** | |

---

## Insurance Carrier Coverage

### Top 20 US Dental Insurance Companies (90%+ Market Coverage):

| Carrier | Market Share | Clearinghouse Coverage |
|---------|-------------|----------------------|
| Delta Dental | 60%+ | ✅ All clearinghouses |
| MetLife | 10% | ✅ All clearinghouses |
| Cigna | 5% | ✅ All clearinghouses |
| Aetna | 5% | ✅ All clearinghouses |
| Guardian | 4% | ✅ All clearinghouses |
| UnitedHealthcare | 3% | ✅ All clearinghouses |
| Humana | 2% | ✅ All clearinghouses |
| Principal | 2% | ✅ All clearinghouses |
| Lincoln Financial | 1% | ✅ All clearinghouses |
| BlueCross BlueShield | 1% | ✅ Most clearinghouses |
| Ameritas | 1% | ✅ Most clearinghouses |
| Sun Life | 1% | ✅ Most clearinghouses |
| Mutual of Omaha | <1% | ✅ Most clearinghouses |

**Note:** The clearinghouse handles ALL of these — you don't need separate integrations with each.

---

## Alternative Approach: White-Label EDI Solutions

If building from scratch seems too complex, consider:

### 1. EDI Partner APIs (Embedded Insurance)
These services handle everything — you just embed their widget/API:

| Provider | Website | Cost | Effort |
|----------|---------|------|--------|
| **CoverMyMeds** (dental) | covermymeds.com | $200-400/mo | 1-2 weeks |
| **Waystar** | waystar.com | $300-500/mo | 2-4 weeks |
| **ZirMed** | zirmed.com | $200-350/mo | 2-3 weeks |

### 2. Stripe Health + Dental Claims (Future Option)
- Stripe is expanding into healthcare billing
- Monitor https://stripe.com/healthcare for dental-specific solutions
- Potential $0.30 + 2.9% per transaction model

---

## My Recommendation for CoreDent

### Best Option: DentalXChange
- **Why:** Startup-friendly, comprehensive API, 1,500+ carriers, reasonable pricing
- **Cost:** ~$200/month + $0.15/claim
- **Timeline:** 6-8 weeks to launch
- **Total Cost to Launch:** $1,500-3,000 (setup + development time)

### Phase 1 (Months 1-2): MVP Insurance
1. Sign up with DentalXChange sandbox
2. Build eligibility check API
3. Build claims submission API
4. Test with 3-5 beta practices
5. Get production credentials

### Phase 2 (Months 3-4): Automated EOB
1. Build remittance webhook processor
2. Auto-post payments to patient accounts
3. Build claims dashboard
4. Build denial workflow management

### Phase 3 (Months 5-6): Advanced Features
1. Pre-authorization workflows
2. Attachment uploads (X-rays with claims)
3. Coordination of benefits (dual insurance)
4. Insurance aging reports

---

## Contact Information Summary

| Company | Contact | Phone | Website |
|---------|---------|-------|---------|
| DentalXChange | api-sales@dentalxchange.com | (888) 474-6220 | dentalxchange.com |
| ChangeEDC | partnerships@changeedc.com | (877) 220-4004 | changeedc.com |
| Open Dental EDI | edi@opendental.com | (801) 374-3232 | opendental.com |
| Availity | providers@availity.com | (866) 282-4548 | availity.com |
| Waystar | sales@waystar.com | (800) 344-0728 | waystar.com |

---

## Next Steps (Start Here)

1. **Email DentalXChange today** — Use the email template above
2. **Sign NDA** — Required before they share API docs
3. **Get sandbox credentials** — Free testing environment
4. **Start building API client** — Takes 1-2 weeks for integration
5. **Budget $200-300/month** — For ongoing clearinghouse fees

**Bottom Line:** Insurance EDI is not that complex technically. The clearinghouse does the heavy lifting (formatting, carrier routing, compliance). You're mainly building REST API integrations and webhook handlers. The 4-8 week estimate is generous — a strong developer could do it in 2-3 weeks with DentalXChange's API.

---

**Prepared By:** Automated Business Analysis  
**Date:** March 31, 2026