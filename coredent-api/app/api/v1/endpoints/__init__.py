"""
API Endpoints Package
"""

from . import auth
from . import patients
from . import appointments
from . import billing
from . import insurance
from . import imaging
from . import treatment
from . import booking
from . import inventory
from . import labs
from . import referrals

__all__ = [
    "auth",
    "patients",
    "appointments",
    "billing",
    "insurance",
    "imaging",
    "treatment",
    "booking",
    "inventory",
    "labs",
    "referrals",
]