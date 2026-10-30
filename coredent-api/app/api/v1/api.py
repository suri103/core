"""
API Router
Combines all endpoint routers
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    patients,
    appointments,
    billing,
    insurance,
    imaging,
    treatment,
    booking,
    inventory,
    labs,
    referrals,
    reports,
    edi,
    staff,
    subscriptions,
    settings,
    communications,
    clinical,
    clinical_notes,
    patient_portal,
    references,
    documents,
    stripe,
    payments,
    automations,
    enterprise,
    platform,
    hardware_bridge,
    migration,
)

api_router = APIRouter()

# Scheduling reference lookups (/providers, /chairs, /appointment-types).
api_router.include_router(references.router, tags=["Reference Data"])

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(patients.router, prefix="/patients", tags=["Patients"])
api_router.include_router(appointments.router, prefix="/appointments", tags=["Appointments"])
api_router.include_router(billing.router, prefix="/billing", tags=["Billing"])
api_router.include_router(stripe.router, prefix="/stripe", tags=["Stripe Payments"])
api_router.include_router(payments.router, prefix="/payments", tags=["Payment Gateways"])
api_router.include_router(insurance.router, prefix="/insurance", tags=["Insurance"])
api_router.include_router(imaging.router, prefix="/imaging", tags=["Imaging"])
api_router.include_router(hardware_bridge.router, prefix="/imaging", tags=["Hardware Bridge & Sensors"])
api_router.include_router(treatment.router, prefix="/treatment", tags=["Treatment Planning"])
api_router.include_router(booking.router, prefix="/booking", tags=["Online Booking"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory Management"])
api_router.include_router(labs.router, prefix="/labs", tags=["Lab Management"])
api_router.include_router(referrals.router, prefix="/referrals", tags=["Referral Management"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reporting & Analytics"])
api_router.include_router(edi.router, prefix="/edi", tags=["Insurance EDI"])
api_router.include_router(staff.router, prefix="/staff", tags=["Practice Staff Management"])
api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["Subscriptions"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(communications.router, prefix="/communications", tags=["Communications"])
api_router.include_router(automations.router, prefix="/automations", tags=["Automations"])
api_router.include_router(enterprise.router, prefix="/enterprise", tags=["Enterprise"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(clinical.router, prefix="/clinical", tags=["Clinical"])
api_router.include_router(clinical_notes.router, prefix="/notes", tags=["Clinical Notes"])
api_router.include_router(patient_portal.router, prefix="/portal", tags=["Patient Portal"])
api_router.include_router(migration.router, prefix="/migration", tags=["Data Migration"])
# Platform (super-admin) console. Cross-tenant by design; every route is
# gated on UserRole.SUPER_ADMIN. Mounted last so its broad prefixes cannot
# shadow any clinic-facing router above.
api_router.include_router(platform.router, prefix="/platform", tags=["Platform (Super Admin)"])