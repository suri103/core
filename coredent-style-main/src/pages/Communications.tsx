/**
 * Communications Page
 * Patient messaging, SMS/email reminders, two-way messaging
 */

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Search,
  Plus,
  MessageSquare,
  Mail,
  Phone,
  Clock,
  Send,
  CheckCircle,
  Trash2,
  Edit,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { useCommunications } from "@/hooks/useCommunications";
import { useToast } from "@/hooks/use-toast";
import type {
  MessageTemplateCreate,
  ReminderScheduleCreate,
  ConversationMessageCreate,
} from "@/services/communicationsApi";

export default function Communications() {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedConversation, setSelectedConversation] = useState<string | null>(null);
  const [newMessage, setNewMessage] = useState("");
  const [activeTab, setActiveTab] = useState("messages");

  // Dialog states
  const [showTemplateDialog, setShowTemplateDialog] = useState(false);
  const [showReminderDialog, setShowReminderDialog] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<string | null>(null);
  const [editingReminder, setEditingReminder] = useState<string | null>(null);

  // Form states for new template
  const [newTemplate, setNewTemplate] = useState<Partial<MessageTemplateCreate>>({
    name: "",
    messageType: "sms",
    subject: "",
    content: "",
    category: "appointment",
    variables: [],
    isActive: true,
    isDefault: false,
  });

  // Form states for new reminder
  const [newReminder, setNewReminder] = useState<Partial<ReminderScheduleCreate>>({
    name: "",
    reminderType: "appointment",
    daysBefore: 1,
    hoursBefore: 0,
    minutesBefore: 0,
    messageType: "sms",
    isActive: true,
    sendOnWeekends: false,
    maxReminders: 3,
    templateId: "",
  });

  // Form states for settings
  // PRODUCT DECISION (safe default): per-practice SMS/email provider
  // credentials have no backend persistence yet (CommunicationSettings model
  // exists but has no table/endpoint; GET /communications/settings returns
  // stats only). Do NOT accept secrets in this UI until persistence + KMS
  // envelope encryption exist. Toggles below are display-only.
  const [smsEnabled, setSmsEnabled] = useState(false);
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [autoRemindersEnabled, setAutoRemindersEnabled] = useState(false);
  const { toast } = useToast();

  const {
    templates,
    templatesLoading,
    fetchTemplates,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    reminders,
    remindersLoading,
    fetchReminders,
    createReminder,
    updateReminder,
    deleteReminder,
    conversations,
    conversationsLoading,
    fetchConversations,
    selectConversation,
    conversationMessages,
    sendConversationMessage,
    summary,
    summaryLoading,
    fetchSummary,
    error,
  } = useCommunications();

  // Load data on mount
  useEffect(() => {
    void Promise.allSettled([
      fetchTemplates(),
      fetchReminders(),
      fetchConversations(),
      fetchSummary(),
    ]);
  }, [fetchTemplates, fetchReminders, fetchConversations, fetchSummary]);

  // Filter conversations by search term
  const filteredConversations = conversations.filter((conv) =>
    conv.patientId.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Handle sending a message in conversation
  const handleSendMessage = async () => {
    if (!selectedConversation || !newMessage.trim()) return;

    const messageData: ConversationMessageCreate = {
      conversationId: selectedConversation,
      senderType: "staff",
      content: newMessage.trim(),
    };

    try {
      const result = await sendConversationMessage(selectedConversation, messageData);
      if (result) {
        setNewMessage("");
      }
    } catch {
      toast({
        title: "Message not sent",
        description: "Could not send the message. It was preserved in the input; please retry.",
        variant: "destructive",
      });
    }
  };

  // Handle creating/updating template
  const handleSaveTemplate = async () => {
    if (!newTemplate.name || !newTemplate.content) return;

    const templateData: MessageTemplateCreate = {
      name: newTemplate.name,
      messageType: newTemplate.messageType as "sms" | "email",
      subject: newTemplate.subject,
      content: newTemplate.content,
      category: newTemplate.category!,
      variables: newTemplate.variables!,
      isActive: newTemplate.isActive!,
      isDefault: newTemplate.isDefault!,
    };

    try {
      if (editingTemplate) {
        await updateTemplate(editingTemplate, templateData);
        toast({ title: "Message template updated" });
      } else {
        await createTemplate(templateData);
        toast({ title: "Message template created" });
      }

      setShowTemplateDialog(false);
      resetTemplateForm();
    } catch {
      toast({
        title: "Template not saved",
        description: "Could not save the template. Your edits are preserved; please retry.",
        variant: "destructive",
      });
    }
  };

  // Handle creating/updating reminder
  const handleSaveReminder = async () => {
    if (!newReminder.name || !newReminder.templateId) return;

    const reminderData: ReminderScheduleCreate = {
      name: newReminder.name,
      reminderType: newReminder.reminderType as "appointment" | "recall" | "treatment",
      daysBefore: newReminder.daysBefore!,
      hoursBefore: newReminder.hoursBefore!,
      minutesBefore: newReminder.minutesBefore!,
      messageType: newReminder.messageType as "sms" | "email",
      isActive: newReminder.isActive!,
      sendOnWeekends: newReminder.sendOnWeekends!,
      maxReminders: newReminder.maxReminders!,
      templateId: newReminder.templateId,
    };

    try {
      if (editingReminder) {
        await updateReminder(editingReminder, reminderData);
        toast({ title: "Reminder schedule updated" });
      } else {
        await createReminder(reminderData);
        toast({ title: "Reminder schedule created" });
      }

      setShowReminderDialog(false);
      resetReminderForm();
    } catch {
      toast({
        title: "Reminder not saved",
        description: "Could not save the reminder. Your edits are preserved; please retry.",
        variant: "destructive",
      });
    }
  };

  const handleDeleteTemplate = async (id: string) => {
    try {
      await deleteTemplate(id);
      toast({ title: "Message template deleted" });
    } catch {
      toast({
        title: "Delete failed",
        description: "Could not delete the template. Please retry.",
        variant: "destructive",
      });
    }
  };

  const handleDeleteReminder = async (id: string) => {
    try {
      await deleteReminder(id);
      toast({ title: "Reminder schedule deleted" });
    } catch {
      toast({
        title: "Delete failed",
        description: "Could not delete the reminder. Please retry.",
        variant: "destructive",
      });
    }
  };

  const handleSelectConversation = async (id: string) => {
    setSelectedConversation(id);
    try {
      await selectConversation(id);
    } catch {
      toast({
        title: "Could not load messages",
        description: "Conversation list is preserved; please retry.",
        variant: "destructive",
      });
    }
  };

  const resetTemplateForm = () => {
    setNewTemplate({
      name: "",
      messageType: "sms",
      subject: "",
      content: "",
      category: "appointment",
      variables: [],
      isActive: true,
      isDefault: false,
    });
    setEditingTemplate(null);
  };

  const resetReminderForm = () => {
    setNewReminder({
      name: "",
      reminderType: "appointment",
      daysBefore: 1,
      hoursBefore: 0,
      minutesBefore: 0,
      messageType: "sms",
      isActive: true,
      sendOnWeekends: false,
      maxReminders: 3,
      templateId: "",
    });
    setEditingReminder(null);
  };

  const openEditTemplate = (template: typeof templates[0]) => {
    setEditingTemplate(template.id);
    setNewTemplate({
      name: template.name,
      messageType: template.messageType,
      subject: template.subject,
      content: template.content,
      category: template.category,
      variables: template.variables,
      isActive: template.isActive,
      isDefault: template.isDefault,
    });
    setShowTemplateDialog(true);
  };

  const openEditReminder = (reminder: typeof reminders[0]) => {
    setEditingReminder(reminder.id);
    setNewReminder({
      name: reminder.name,
      reminderType: reminder.reminderType,
      daysBefore: reminder.daysBefore,
      hoursBefore: reminder.hoursBefore,
      minutesBefore: reminder.minutesBefore,
      messageType: reminder.messageType,
      isActive: reminder.isActive,
      sendOnWeekends: reminder.sendOnWeekends,
      maxReminders: reminder.maxReminders,
      templateId: reminder.templateId,
    });
    setShowReminderDialog(true);
  };

  // Format reminder time
  const formatReminderTime = (reminder: typeof reminders[0]) => {
    const parts = [];
    if (reminder.daysBefore > 0) parts.push(`${reminder.daysBefore} day(s) before`);
    if (reminder.hoursBefore > 0) parts.push(`${reminder.hoursBefore} hour(s) before`);
    if (reminder.minutesBefore > 0) parts.push(`${reminder.minutesBefore} minute(s) before`);
    return parts.join(", ") || "At scheduled time";
  };

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Patient Communications</h1>
          <p className="text-muted-foreground">Manage messages, reminders, and notifications</p>
        </div>
        <Button onClick={() => setShowTemplateDialog(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Message
        </Button>
      </div>

      {error && (
        <Alert variant="destructive" role="alert">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Communication data unavailable</AlertTitle>
          <AlertDescription>
            {error.message}. Existing data is preserved; retry after the service recovers.
          </AlertDescription>
        </Alert>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Unread Messages</CardTitle>
            <MessageSquare className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-500">
              {summaryLoading ? <Loader2 className="h-6 w-6 animate-spin" /> : summary?.unreadMessages || 0}
            </div>
            <p className="text-xs text-muted-foreground">needs attention</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Sent Today</CardTitle>
            <Send className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {summaryLoading ? <Loader2 className="h-6 w-6 animate-spin" /> : summary?.messages.totalSent || 0}
            </div>
            <p className="text-xs text-muted-foreground">messages sent</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Scheduled</CardTitle>
            <Clock className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-500">
              {summaryLoading ? <Loader2 className="h-6 w-6 animate-spin" /> : summary?.reminders.pending || 0}
            </div>
            <p className="text-xs text-muted-foreground">reminders pending</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Delivery Rate</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-500">
              {summaryLoading ? <Loader2 className="h-6 w-6 animate-spin" /> : `${summary?.messages.deliveryRate || 0}%`}
            </div>
            <p className="text-xs text-muted-foreground">successful deliveries</p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList>
          <TabsTrigger value="messages">Messages</TabsTrigger>
          <TabsTrigger value="reminders">Reminders</TabsTrigger>
          <TabsTrigger value="templates">Templates</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>

        <TabsContent value="messages">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Conversation List */}
            <Card className="lg:col-span-1">
              <CardHeader>
                <CardTitle className="text-lg">Conversations</CardTitle>
                <div className="relative mt-2">
                  <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search messages..."
                    className="pl-10"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
              </CardHeader>
              <CardContent className="p-0">
                {conversationsLoading ? (
                  <div className="flex items-center justify-center p-8">
                    <Loader2 className="h-6 w-6 animate-spin" />
                  </div>
                ) : (
                  <div className="divide-y">
                    {filteredConversations.map((conv) => (
                      <div
                        key={conv.id}
                        className={`p-4 cursor-pointer hover:bg-muted/50 ${
                          selectedConversation === conv.id ? "bg-muted" : ""
                        }`}
                        onClick={() => {
                          void handleSelectConversation(conv.id);
                        }}
                      >
                        <div className="flex justify-between items-start">
                          <div>
                            <p className="font-medium">Patient {conv.patientId.slice(0, 8)}...</p>
                            <p className="text-sm text-muted-foreground truncate">
                              {conv.lastMessagePreview || "No messages yet"}
                            </p>
                          </div>
                          <div className="text-right">
                            <p className="text-xs text-muted-foreground">
                              {conv.lastMessageAt
                                ? new Date(conv.lastMessageAt).toLocaleTimeString()
                                : ""}
                            </p>
                            {conv.unreadCount > 0 && (
                              <Badge className="mt-1 bg-blue-500">{conv.unreadCount}</Badge>
                            )}
                          </div>
                        </div>
                        <div className="mt-2">
                          <Badge variant="outline" className="text-xs">
                            {conv.channel === "sms" ? (
                              <Phone className="h-3 w-3 mr-1" />
                            ) : (
                              <Mail className="h-3 w-3 mr-1" />
                            )}
                            {conv.channel.toUpperCase()}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Message Thread */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>
                  {selectedConversation
                    ? `Conversation with Patient ${selectedConversation.slice(0, 8)}...`
                    : "Select a conversation"}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {selectedConversation ? (
                  <>
                    <div className="max-h-[400px] overflow-y-auto space-y-4">
                      {conversationMessages.map((msg) => (
                        <div
                          key={msg.id}
                          className={`flex ${
                            msg.senderType === "staff" ? "justify-end" : "justify-start"
                          }`}
                        >
                          <div
                            className={`rounded-lg p-3 max-w-[70%] ${
                              msg.senderType === "staff"
                                ? "bg-primary text-primary-foreground"
                                : "bg-muted"
                            }`}
                          >
                            <p className="text-sm">{msg.content}</p>
                            <p className="text-xs mt-1 opacity-70">
                              {new Date(msg.createdAt).toLocaleString()}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="flex gap-2 mt-4">
                      <Textarea
                        placeholder="Type your message..."
                        className="min-h-[80px]"
                        value={newMessage}
                        onChange={(e) => setNewMessage(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && !e.shiftKey) {
                            e.preventDefault();
                            void handleSendMessage();
                          }
                        }}
                      />
                      <Button className="self-end" onClick={() => void handleSendMessage()}>
                        <Send className="h-4 w-4" />
                      </Button>
                    </div>
                  </>
                ) : (
                  <div className="flex items-center justify-center h-64 text-muted-foreground">
                    <div className="text-center">
                      <MessageSquare className="h-12 w-12 mx-auto mb-4 opacity-50" />
                      <p>Select a conversation to view messages</p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="reminders">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Reminder Schedules</CardTitle>
              <Button onClick={() => setShowReminderDialog(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Add Reminder
              </Button>
            </CardHeader>
            <CardContent className="p-0">
              {remindersLoading ? (
                <div className="flex items-center justify-center p-8">
                  <Loader2 className="h-6 w-6 animate-spin" />
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Timing</TableHead>
                      <TableHead>Channel</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {reminders.map((reminder) => (
                      <TableRow key={reminder.id}>
                        <TableCell className="font-medium">{reminder.name}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{reminder.reminderType}</Badge>
                        </TableCell>
                        <TableCell>{formatReminderTime(reminder)}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{reminder.messageType.toUpperCase()}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge className={reminder.isActive ? "bg-green-500" : "bg-gray-500"}>
                            {reminder.isActive ? "Active" : "Inactive"}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => openEditReminder(reminder)}
                            >
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => void handleDeleteReminder(reminder.id)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="templates">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Message Templates</CardTitle>
              <Button onClick={() => { resetTemplateForm(); setShowTemplateDialog(true); }}>
                <Plus className="mr-2 h-4 w-4" />
                Add Template
              </Button>
            </CardHeader>
            <CardContent>
              {templatesLoading ? (
                <div className="flex items-center justify-center p-8">
                  <Loader2 className="h-6 w-6 animate-spin" />
                </div>
              ) : (
                <div className="space-y-4">
                  {templates.map((template) => (
                    <div key={template.id} className="border rounded-lg p-4">
                      <div className="flex justify-between items-start">
                        <div>
                          <div className="flex items-center gap-2">
                            <h4 className="font-medium">{template.name}</h4>
                            {template.isDefault && (
                              <Badge variant="secondary" className="text-xs">Default</Badge>
                            )}
                          </div>
                          <div className="flex gap-2 mt-1">
                            <Badge variant="outline" className="text-xs">
                              {template.messageType.toUpperCase()}
                            </Badge>
                            {template.category && (
                              <Badge variant="outline" className="text-xs">
                                {template.category}
                              </Badge>
                            )}
                          </div>
                          <p className="text-sm text-muted-foreground mt-2 line-clamp-2">
                            {template.content}
                          </p>
                          {template.variables && template.variables.length > 0 && (
                            <p className="text-xs text-muted-foreground mt-1">
                              Variables: {template.variables.join(", ")}
                            </p>
                          )}
                        </div>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => openEditTemplate(template)}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => void handleDeleteTemplate(template.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="settings">
          <Card>
            <CardHeader>
              <CardTitle>Communication Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* SMS Settings */}
              <div className="border rounded-lg p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">SMS Notifications</p>
                    <p className="text-sm text-muted-foreground">Enable SMS messaging via Twilio</p>
                  </div>
                  <Switch checked={smsEnabled} onCheckedChange={setSmsEnabled} />
                </div>
                {smsEnabled && (
                  <div className="space-y-4 pt-4 border-t">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label>Account SID</Label>
                        <Input placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" />
                      </div>
                      <div>
                        <Label>Auth Token</Label>
                        <Input type="password" placeholder="Your Twilio auth token" />
                      </div>
                      <div>
                        <Label>Phone Number</Label>
                        <Input placeholder="+1234567890" />
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Email Settings */}
              <div className="border rounded-lg p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Email Notifications</p>
                    <p className="text-sm text-muted-foreground">Enable email messaging via SendGrid</p>
                  </div>
                  <Switch checked={emailEnabled} onCheckedChange={setEmailEnabled} />
                </div>
                {emailEnabled && (
                  <div className="space-y-4 pt-4 border-t">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label>API Key</Label>
                        <Input type="password" placeholder="Your SendGrid API key" />
                      </div>
                      <div>
                        <Label>From Email</Label>
                        <Input type="email" placeholder="noreply@yourpractice.com" />
                      </div>
                      <div>
                        <Label>From Name</Label>
                        <Input placeholder="Your Practice Name" />
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Auto Reminder Settings */}
              <div className="border rounded-lg p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Auto Reminders</p>
                    <p className="text-sm text-muted-foreground">Send automatic appointment reminders</p>
                  </div>
                  <Switch checked={autoRemindersEnabled} onCheckedChange={setAutoRemindersEnabled} />
                </div>
                {autoRemindersEnabled && (
                  <div className="space-y-4 pt-4 border-t">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label>Default Lead Time (hours)</Label>
                        <Input type="number" defaultValue={24} min={1} max={168} />
                      </div>
                      <div>
                        <Label>Max Reminders</Label>
                        <Input type="number" defaultValue={3} min={1} max={10} />
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Provider settings are managed by your administrator</AlertTitle>
                <AlertDescription>
                  SMS/email delivery is configured server-side (Twilio/SendGrid). Per-practice
                  credential storage is not available in this build, so these toggles are
                  display-only and nothing here is persisted.
                </AlertDescription>
              </Alert>
              <Button
                className="w-full"
                disabled
                title="Per-practice provider settings are not yet persisted by the API"
              >
                Save Settings (unavailable)
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Template Dialog */}
      <Dialog open={showTemplateDialog} onOpenChange={setShowTemplateDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editingTemplate ? "Edit Template" : "Create Template"}</DialogTitle>
            <DialogDescription>
              Configure reusable SMS or email content for patient communication workflows.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Template Name</Label>
              <Input
                value={newTemplate.name}
                onChange={(e) => setNewTemplate({ ...newTemplate, name: e.target.value })}
                placeholder="Appointment Reminder"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Message Type</Label>
                <Select
                  value={newTemplate.messageType}
                  onValueChange={(v) => setNewTemplate({ ...newTemplate, messageType: v as "sms" | "email" })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sms">SMS</SelectItem>
                    <SelectItem value="email">Email</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Category</Label>
                <Select
                  value={newTemplate.category}
                  onValueChange={(v) => setNewTemplate({ ...newTemplate, category: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="appointment">Appointment</SelectItem>
                    <SelectItem value="recall">Recall</SelectItem>
                    <SelectItem value="treatment">Treatment</SelectItem>
                    <SelectItem value="billing">Billing</SelectItem>
                    <SelectItem value="marketing">Marketing</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            {newTemplate.messageType === "email" && (
              <div>
                <Label>Subject</Label>
                <Input
                  value={newTemplate.subject}
                  onChange={(e) => setNewTemplate({ ...newTemplate, subject: e.target.value })}
                  placeholder="Email subject line"
                />
              </div>
            )}
            <div>
              <Label>Content</Label>
              <Textarea
                value={newTemplate.content}
                onChange={(e) => setNewTemplate({ ...newTemplate, content: e.target.value })}
                placeholder="Hi [patient_name], this is a reminder..."
                rows={6}
              />
              <p className="text-xs text-muted-foreground mt-1">
                Use variables like [patient_name], [date], [time], [practice_name]
              </p>
            </div>
            <div className="flex items-center space-x-2">
              <Switch
                id="is-active"
                checked={newTemplate.isActive}
                onCheckedChange={(v) => setNewTemplate({ ...newTemplate, isActive: v })}
              />
              <Label htmlFor="is-active">Active</Label>
            </div>
            <div className="flex items-center space-x-2">
              <Switch
                id="is-default"
                checked={newTemplate.isDefault}
                onCheckedChange={(v) => setNewTemplate({ ...newTemplate, isDefault: v })}
              />
              <Label htmlFor="is-default">Set as default for this type</Label>
            </div>
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setShowTemplateDialog(false)}>
                Cancel
              </Button>
              <Button onClick={() => void handleSaveTemplate()} disabled={templatesLoading}>
                {templatesLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save Template"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Reminder Dialog */}
      <Dialog open={showReminderDialog} onOpenChange={setShowReminderDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editingReminder ? "Edit Reminder" : "Create Reminder Schedule"}</DialogTitle>
            <DialogDescription>
              Choose when automated patient reminders are sent and which template they use.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Reminder Name</Label>
              <Input
                value={newReminder.name}
                onChange={(e) => setNewReminder({ ...newReminder, name: e.target.value })}
                placeholder="1 Day Before Appointment"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Reminder Type</Label>
                <Select
                  value={newReminder.reminderType}
                  onValueChange={(v) => setNewReminder({ ...newReminder, reminderType: v as "appointment" | "recall" | "treatment" })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="appointment">Appointment</SelectItem>
                    <SelectItem value="recall">Recall</SelectItem>
                    <SelectItem value="treatment">Treatment</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Message Type</Label>
                <Select
                  value={newReminder.messageType}
                  onValueChange={(v) => setNewReminder({ ...newReminder, messageType: v as "sms" | "email" })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sms">SMS</SelectItem>
                    <SelectItem value="email">Email</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label>Template</Label>
              <Select
                value={newReminder.templateId}
                onValueChange={(v) => setNewReminder({ ...newReminder, templateId: v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a template" />
                </SelectTrigger>
                <SelectContent>
                  {templates.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <Label>Days Before</Label>
                <Input
                  type="number"
                  min={0}
                  value={newReminder.daysBefore}
                  onChange={(e) => setNewReminder({ ...newReminder, daysBefore: parseInt(e.target.value) || 0 })}
                />
              </div>
              <div>
                <Label>Hours Before</Label>
                <Input
                  type="number"
                  min={0}
                  value={newReminder.hoursBefore}
                  onChange={(e) => setNewReminder({ ...newReminder, hoursBefore: parseInt(e.target.value) || 0 })}
                />
              </div>
              <div>
                <Label>Minutes Before</Label>
                <Input
                  type="number"
                  min={0}
                  value={newReminder.minutesBefore}
                  onChange={(e) => setNewReminder({ ...newReminder, minutesBefore: parseInt(e.target.value) || 0 })}
                />
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <Switch
                id="reminder-active"
                checked={newReminder.isActive}
                onCheckedChange={(v) => setNewReminder({ ...newReminder, isActive: v })}
              />
              <Label htmlFor="reminder-active">Active</Label>
            </div>
            <div className="flex items-center space-x-2">
              <Switch
                id="send-weekends"
                checked={newReminder.sendOnWeekends}
                onCheckedChange={(v) => setNewReminder({ ...newReminder, sendOnWeekends: v })}
              />
              <Label htmlFor="send-weekends">Send on weekends</Label>
            </div>
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setShowReminderDialog(false)}>
                Cancel
              </Button>
              <Button onClick={() => void handleSaveReminder()} disabled={remindersLoading}>
                {remindersLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save Reminder"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}