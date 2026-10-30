from pydantic import BaseModel
from typing import List

class AppointmentTypeCount(BaseModel):
    type: str
    count: int
    color: str

class AppointmentDayCount(BaseModel):
    day: str
    count: int

class AppointmentsSummary(BaseModel):
    total: int
    completed: int
    cancelled: int
    noShow: int
    scheduled: int
    completionRate: float
    noShowRate: float
    byType: List[AppointmentTypeCount]
    byDay: List[AppointmentDayCount]

class MonthRevenue(BaseModel):
    month: str
    revenue: float
    collected: float

class ProcedureRevenue(BaseModel):
    procedure: str
    revenue: float
    count: int

class RevenueSummary(BaseModel):
    totalRevenue: float
    totalCollected: float
    totalOutstanding: float
    averagePerVisit: float
    byMonth: List[MonthRevenue]
    byProcedure: List[ProcedureRevenue]

class MonthAcceptance(BaseModel):
    month: str
    proposed: int
    accepted: int

class TreatmentAcceptance(BaseModel):
    proposedPlans: int
    acceptedPlans: int
    completedPlans: int
    acceptanceRate: float
    completionRate: float
    byMonth: List[MonthAcceptance]

class HourUtilization(BaseModel):
    hour: str
    utilization: float

class ChairUtilizationMetric(BaseModel):
    chair: str
    utilization: float
    appointments: int

class DayUtilization(BaseModel):
    day: str
    utilization: float

class ChairUtilizationSummary(BaseModel):
    totalChairs: int
    averageUtilization: float
    peakHours: List[HourUtilization]
    byChair: List[ChairUtilizationMetric]
    byDayOfWeek: List[DayUtilization]

class DashboardMetricsResponse(BaseModel):
    appointments: AppointmentsSummary
    revenue: RevenueSummary
    treatmentAcceptance: TreatmentAcceptance
    chairUtilization: ChairUtilizationSummary
