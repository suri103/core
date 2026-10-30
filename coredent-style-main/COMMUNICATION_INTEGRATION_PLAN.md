# Communication Features Integration Plan

## Overview
This document outlines the comprehensive integration of communication/notification features across the CoreDent SaaS application. The Communications module has been implemented with full CRUD functionality for templates, reminders, messages, and settings. This plan identifies all touchpoints where these features should be integrated.

## ✅ Completed Components

### 1. Communications Page (`/communications`)
- **Templates Tab**: Full CRUD for message templates with variables
- **Reminders Tab**: Schedule management for automated reminders
- **Messages Tab**: Two-way patient messaging with conversation threads
- **Settings Tab**: SMS/Email provider configuration

### 2. Notification Center
- Global notification bell in header
- Real-time notification display
- Mark as read/delete functionality
- Quick navigation to Communications

### 3. Backend API
- Full REST API for all communication entities
- Summary statistics endpoint
- Settings management

## 🔧 Integration Points

### 1. Appointments Page
**Current State**: Has `useSendAppointmentReminder` hook reference
**Required Integration**:
- Connect to Communications reminders system
- Add "Send Reminder Now" button that triggers immediate SMS/Email
- Show reminder status in appointment details
- Link to Communications for reminder template selection

**Implementation**:
```tsx
// In Appointments.tsx
const handleSendReminder = async (appointmentId: string) => {
  // Use communications API to send immediate reminder
  await communicationsApi.messages.send({
    patientId: appointment.patientId,
    messageType: 'sms',
    templateId: defaultReminderTemplateId,
    variables: {
      patient_name: appointment.patientName,
      appointment_date: appointment.date,
      appointment_time: appointment.time
    }
  });
};
```

### 2. Billing Page
**Current State**: No communication integration
**Required Integration**:
- Send payment reminders via SMS/Email
- Email invoices automatically
- Payment receipt notifications
- Overdue balance alerts

**Implementation**:
- Add "Send Payment Reminder" button in billing table
- Integrate with Communications templates for billing messages
- Show communication history in patient billing details

### 3. Patient Profile
**Current State**: Shows patient info, no communication history
**Required Integration**:
- Add "Communication History" tab
- Show all messages, reminders sent to patient
- Quick action buttons to send message/reminder
- Display patient communication preferences

**Implementation**:
```tsx
// New PatientCommunicationTab.tsx
const PatientCommunicationTab = ({ patientId }) => {
  const { messages, reminders } = useCommunications();
  const filteredMessages = messages.filter(m => m.patientId === patientId);
  // Display communication timeline
};
```

### 4. Dashboard
**Current State**: Shows basic statistics
**Required Integration**:
- Add notification bell to header (NotificationCenter component)
- Show communication statistics widget
- Display recent messages count
- Quick actions for common communication tasks

### 5. Settings Page
**Current State**: Has practice settings
**Required Integration**:
- Add "Communication Preferences" section
- Link to Communications settings tab
- Global notification preferences
- Opt-in/opt-out settings for automated reminders

### 6. Marketing Page
**Current State**: Marketing campaigns page
**Required Integration**:
- Use Communications templates for marketing messages
- Bulk email/SMS campaign functionality
- Campaign performance tracking
- Patient engagement metrics

### 7. Referrals Page
**Current State**: Referral tracking
**Required Integration**:
- Notify referring doctors via email
- Send referral status updates to patients
- Automated follow-up reminders
- Communication log for each referral

### 8. Lab Management
**Current State**: Lab case tracking
**Required Integration**:
- Notify when lab results are ready
- Alert staff about pending lab work
- Patient notifications for lab updates
- Communication history per lab case

### 9. Treatment Plans
**Current State**: Treatment plan management
**Required Integration**:
- Send treatment acceptance reminders
- Automated follow-up for pending treatments
- Patient education messages
- Treatment completion notifications

### 10. Staff Management
**Current State**: Staff CRUD operations
**Required Integration**:
- Task assignment notifications
- Shift change alerts
- Internal staff messaging
- Invitation email customization

## 📋 Implementation Priority

### Phase 1 (High Priority - Week 1)
1. ✅ Communications Page - COMPLETED
2. ✅ Notification Center - COMPLETED
3. Appointments integration
4. Patient Profile communication tab

### Phase 2 (Medium Priority - Week 2)
5. Billing integration
6. Dashboard widgets
7. Settings integration
8. Marketing integration

### Phase 3 (Standard Priority - Week 3)
9. Referrals integration
10. Lab Management integration
11. Treatment Plans integration
12. Staff Management integration

## 🔌 Shared Components

### useNotification Hook
Create a shared hook for triggering notifications:

```tsx
// hooks/useNotification.ts
export function useNotification() {
  const { sendMessage } = useCommunications();
  
  const sendAppointmentReminder = async (appointment, templateId) => {
    // Send reminder using Communications API
  };
  
  const sendBillingNotification = async (patient, type, data) => {
    // Send billing notification
  };
  
  const sendLabNotification = async (labCase, type) => {
    // Send lab notification
  };
  
  return {
    sendAppointmentReminder,
    sendBillingNotification,
    sendLabNotification,
  };
}
```

### CommunicationButton Component
Reusable component for sending messages:

```tsx
// components/CommunicationButton.tsx
export function CommunicationButton({ patientId, type, templateId }) {
  const [open, setOpen] = useState(false);
  const { sendMessage } = useCommunications();
  
  const handleSend = async () => {
    await sendMessage({ patientId, templateId, type });
    setOpen(false);
  };
  
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Mail className="h-4 w-4 mr-2" />
          Send Message
        </Button>
      </DialogTrigger>
      <DialogContent>
        {/* Message composition UI */}
      </DialogContent>
    </Dialog>
  );
}
```

## 🧪 Testing Checklist

- [ ] Test reminder sending from Appointments page
- [ ] Test billing notifications
- [ ] Test patient communication history
- [ ] Test notification center real-time updates
- [ ] Test template variable substitution
- [ ] Test SMS/Email delivery (use test mode)
- [ ] Test notification preferences
- [ ] Test cross-page communication consistency

## 📊 Success Metrics

1. **Reminder Delivery Rate**: >95% successful deliveries
2. **Patient Response Time**: Average response <2 hours
3. **Template Usage**: >80% of messages use templates
4. **Notification Engagement**: >60% open rate
5. **Communication Coverage**: 100% of patient touchpoints

## 🚀 Deployment Notes

1. Ensure SMS/Email provider credentials are configured
2. Set up webhook endpoints for delivery status
3. Configure rate limiting for bulk messages
4. Enable communication logging for compliance
5. Set up monitoring for delivery failures

## 📝 Compliance Considerations

- All patient communications must be logged
- Opt-out mechanisms required for marketing messages
- HIPAA compliance for medical communications
- Data retention policies for message history
- Audit trail for all sent communications