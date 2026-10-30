// Internationalization utilities for multi-language support

type Translations = Record<string, Record<string, unknown>>;

interface I18nConfig {
  defaultLocale: string;
  supportedLocales: string[];
  translations: Translations;
}

class I18n {
  private currentLocale: string;
  private defaultLocale: string;
  private supportedLocales: string[];
  private translations: Translations;

  constructor(config: I18nConfig) {
    this.defaultLocale = config.defaultLocale;
    this.supportedLocales = config.supportedLocales;
    this.translations = config.translations;
    
    // Try to get locale from localStorage or browser
    const savedLocale = localStorage.getItem('locale');
    const browserLocale = navigator.language.split('-')[0];
    
    this.currentLocale = 
      savedLocale && this.supportedLocales.includes(savedLocale)
        ? savedLocale
        : this.supportedLocales.includes(browserLocale)
        ? browserLocale
        : this.defaultLocale;
  }

  t(key: string, params?: Record<string, string | number>): string {
    const keys = key.split('.');
    let translation: any = this.translations[this.currentLocale];

    // Navigate through nested keys
    for (const k of keys) {
      if (translation && typeof translation === 'object') {
        translation = translation[k];
      } else {
        translation = undefined;
        break;
      }
    }

    // Fallback to default locale
    if (!translation) {
      translation = this.translations[this.defaultLocale];
      for (const k of keys) {
        if (translation && typeof translation === 'object') {
          translation = translation[k];
        } else {
          translation = key; // Return key if not found
          break;
        }
      }
    }

    // Replace parameters
    if (params && typeof translation === 'string') {
      Object.entries(params).forEach(([param, value]) => {
        translation = translation.replace(`{{${param}}}`, String(value));
      });
    }

    return translation || key;
  }

  setLocale(locale: string): void {
    if (this.supportedLocales.includes(locale)) {
      this.currentLocale = locale;
      localStorage.setItem('locale', locale);
      document.documentElement.lang = locale;
      
      // Dispatch event for components to react
      window.dispatchEvent(new CustomEvent('localechange', { detail: { locale } }));
    }
  }

  getLocale(): string {
    return this.currentLocale;
  }

  getSupportedLocales(): string[] {
    return this.supportedLocales;
  }

  addTranslations(locale: string, translations: Record<string, any>): void {
    if (!this.translations[locale]) {
      this.translations[locale] = {};
    }
    this.translations[locale] = { ...this.translations[locale], ...translations };
  }
}

// Default translations
const translations: Translations = {
  en: {
    common: {
      save: 'Save',
      cancel: 'Cancel',
      delete: 'Delete',
      edit: 'Edit',
      add: 'Add',
      search: 'Search',
      loading: 'Loading...',
      error: 'Error',
      success: 'Success',
      confirm: 'Confirm',
      back: 'Back',
      next: 'Next',
      previous: 'Previous',
      close: 'Close',
    },
    auth: {
      login: 'Sign In',
      logout: 'Sign Out',
      email: 'Email',
      password: 'Password',
      forgotPassword: 'Forgot Password?',
      rememberMe: 'Remember Me',
      loginError: 'Invalid email or password',
      sessionExpired: 'Your session has expired. Please sign in again.',
    },
    dashboard: {
      title: 'Dashboard',
      welcome: 'Welcome back, {{name}}!',
      todayAppointments: "Today's Appointments",
      upcomingAppointments: 'Upcoming Appointments',
      recentPatients: 'Recent Patients',
    },
    patients: {
      title: 'Patients',
      addPatient: 'Add Patient',
      editPatient: 'Edit Patient',
      deletePatient: 'Delete Patient',
      patientDetails: 'Patient Details',
      firstName: 'First Name',
      lastName: 'Last Name',
      dateOfBirth: 'Date of Birth',
      phone: 'Phone',
      email: 'Email',
      address: 'Address',
      status: 'Status',
      active: 'Active',
      inactive: 'Inactive',
    },
    appointments: {
      title: 'Appointments',
      schedule: 'Schedule',
      newAppointment: 'New Appointment',
      editAppointment: 'Edit Appointment',
      cancelAppointment: 'Cancel Appointment',
      patient: 'Patient',
      provider: 'Provider',
      date: 'Date',
      time: 'Time',
      duration: 'Duration',
      type: 'Type',
      status: 'Status',
      notes: 'Notes',
    },
    billing: {
      title: 'Billing',
      invoices: 'Invoices',
      payments: 'Payments',
      createInvoice: 'Create Invoice',
      invoiceNumber: 'Invoice Number',
      amount: 'Amount',
      dueDate: 'Due Date',
      paid: 'Paid',
      unpaid: 'Unpaid',
      overdue: 'Overdue',
    },
    settings: {
      title: 'Settings',
      general: 'General',
      profile: 'Profile',
      security: 'Security',
      notifications: 'Notifications',
      language: 'Language',
      theme: 'Theme',
      saveChanges: 'Save Changes',
    },
    errors: {
      notFound: 'Page not found',
      serverError: 'Server error occurred',
      networkError: 'Network error. Please check your connection.',
      unauthorized: 'You are not authorized to access this resource',
      validationError: 'Please check your input and try again',
    },
  },
  es: {
    common: {
      save: 'Guardar',
      cancel: 'Cancelar',
      delete: 'Eliminar',
      edit: 'Editar',
      add: 'Agregar',
      search: 'Buscar',
      loading: 'Cargando...',
      error: 'Error',
      success: 'Éxito',
      confirm: 'Confirmar',
      back: 'Atrás',
      next: 'Siguiente',
      previous: 'Anterior',
      close: 'Cerrar',
    },
    auth: {
      login: 'Iniciar Sesión',
      logout: 'Cerrar Sesión',
      email: 'Correo Electrónico',
      password: 'Contraseña',
      forgotPassword: '¿Olvidaste tu contraseña?',
      rememberMe: 'Recuérdame',
      loginError: 'Correo o contraseña inválidos',
      sessionExpired: 'Tu sesión ha expirado. Por favor inicia sesión nuevamente.',
    },
    dashboard: {
      title: 'Panel de Control',
      welcome: '¡Bienvenido de nuevo, {{name}}!',
      todayAppointments: 'Citas de Hoy',
      upcomingAppointments: 'Próximas Citas',
      recentPatients: 'Pacientes Recientes',
    },
    patients: {
      title: 'Pacientes',
      addPatient: 'Agregar Paciente',
      editPatient: 'Editar Paciente',
      deletePatient: 'Eliminar Paciente',
      patientDetails: 'Detalles del Paciente',
      firstName: 'Nombre',
      lastName: 'Apellido',
      dateOfBirth: 'Fecha de Nacimiento',
      phone: 'Teléfono',
      email: 'Correo',
      address: 'Dirección',
      status: 'Estado',
      active: 'Activo',
      inactive: 'Inactivo',
    },
  },
  hi: {
    common: {
      save: 'सहेजें',
      cancel: 'रद्द करें',
      delete: 'हटाएं',
      edit: 'संपादित करें',
      add: 'जोड़ें',
      search: 'खोजें',
      loading: 'लोड हो रहा है...',
      error: 'त्रुटि',
      success: 'सफल',
      confirm: 'पुष्टि करें',
      back: 'वापस',
      next: 'आगे',
      previous: 'पिछला',
      close: 'बंद करें',
      submit: 'जमा करें',
      actions: 'कार्रवाई',
      yes: 'हाँ',
      no: 'नहीं',
      ok: 'ठीक है',
    },
    auth: {
      login: 'साइन इन करें',
      logout: 'साइन आउट',
      email: 'ईमेल',
      password: 'पासवर्ड',
      forgotPassword: 'पासवर्ड भूल गए?',
      rememberMe: 'मुझे याद रखें',
      loginError: 'अमान्य ईमेल या पासवर्ड',
      sessionExpired: 'आपका सत्र समाप्त हो गया। कृपया पुनः साइन इन करें।',
      resetPassword: 'पासवर्ड रीसेट करें',
      role: 'भूमिका',
    },
    dashboard: {
      title: 'डैशबोर्ड',
      welcome: '{{name}}, वापसी पर स्वागत!',
      todayAppointments: 'आज की अपॉइंटमेंट',
      upcomingAppointments: 'आगामी अपॉइंटमेंट',
      recentPatients: 'हाल के रोगी',
      totalRevenue: 'कुल राजस्व',
      pendingInvoices: 'बकाया चालान',
    },
    patients: {
      title: 'रोगी',
      addPatient: 'रोगी जोड़ें',
      editPatient: 'रोगी संपादित करें',
      deletePatient: 'रोगी हटाएं',
      patientDetails: 'रोगी विवरण',
      firstName: 'पहला नाम',
      lastName: 'उपनाम',
      dateOfBirth: 'जन्म तिथि',
      phone: 'फ़ोन',
      email: 'ईमेल',
      address: 'पता',
      status: 'स्थिति',
      active: 'सक्रिय',
      inactive: 'निष्क्रिय',
      searchPatient: 'रोगी खोजें',
      noPatients: 'कोई रोगी नहीं मिला',
      patientName: 'रोगी का नाम',
      medicalHistory: 'चिकित्सा इतिहास',
      allergies: 'एलर्जी',
      medications: 'दवाएं',
    },
    appointments: {
      title: 'अपॉइंटमेंट',
      schedule: 'अनुसूची',
      newAppointment: 'नई अपॉइंटमेंट',
      editAppointment: 'अपॉइंटमेंट संपादित करें',
      cancelAppointment: 'अपॉइंटमेंट रद्द करें',
      patient: 'रोगी',
      provider: 'चिकित्सक',
      date: 'तिथि',
      time: 'समय',
      duration: 'अवधि',
      type: 'प्रकार',
      status: 'स्थिति',
      notes: 'नोट्स',
      checkup: 'जांच',
      cleaning: 'सफाई',
      filling: 'भराई',
      extraction: 'निकासी',
      rootCanal: 'रूट कैनाल',
      consultation: 'परामर्श',
      confirmed: 'पुष्टि हुई',
      pending: 'बकाया',
      completed: 'पूर्ण',
    },
    billing: {
      title: 'बिलिंग',
      invoices: 'चालान',
      payments: 'भुगतान',
      createInvoice: 'चालान बनाएं',
      invoiceNumber: 'चालान संख्या',
      amount: 'राशि',
      dueDate: 'नियत तिथि',
      paid: 'भुगतान हुआ',
      unpaid: 'अभुक्तान',
      overdue: 'अतिदेय',
      gst: 'GST',
      gstin: 'GSTIN',
      taxAmount: 'कर राशि',
      totalAmount: 'कुल राशि',
      discount: 'छूट',
      subtotal: 'उप-योग',
      paymentMethod: 'भुगतान विधि',
      upi: 'UPI',
      card: 'कार्ड',
      cash: 'नकद',
      netbanking: 'नेट बैंकिंग',
    },
    settings: {
      title: 'सेटिंग्स',
      general: 'सामान्य',
      profile: 'प्रोफ़ाइल',
      security: 'सुरक्षा',
      notifications: 'सूचनाएं',
      language: 'भाषा',
      theme: 'थीम',
      saveChanges: 'बदलाव सहेजें',
      practiceName: 'क्लिनिक का नाम',
      darkMode: 'डार्क मोड',
      lightMode: 'लाइट मोड',
    },
    errors: {
      notFound: 'पेज नहीं मिला',
      serverError: 'सर्वर त्रुटि हुई',
      networkError: 'नेटवर्क त्रुटि। कृपया अपना कनेक्शन जांचें।',
      unauthorized: 'आप इस संसाधन तक पहुंच के लिए अधिकृत नहीं हैं',
      validationError: 'कृपया अपना इनपुट जांचें और पुनः प्रयास करें',
    },
    navigation: {
      patients: 'रोगी',
      appointments: 'अपॉइंटमेंट',
      billing: 'बिलिंग',
      imaging: 'इमेजिंग',
      lab: 'लैब',
      referrals: 'रेफरल',
      inventory: 'इन्वेंटरी',
      reports: 'रिपोर्ट',
      settings: 'सेटिंग्स',
    },
    payments: {
      title: 'भुगतान',
      processPayment: 'भुगतान प्रक्रिया करें',
      payWithUPI: 'UPI से भुगतान करें',
      payNow: 'अभी भुगतान करें',
      processing: 'प्रक्रिया हो रही है...',
      paymentSuccessful: 'भुगतान सफल!',
      paymentFailed: 'भुगतान विफल',
      paymentId: 'भुगतान ID',
      amountINR: 'राशि (₹)',
    },
  },
};

// Create global i18n instance
export const i18n = new I18n({
  defaultLocale: 'en',
  supportedLocales: ['en', 'es', 'hi'],
  translations,
});

// React hook for i18n
export function useTranslation() {
  const [locale, setLocale] = React.useState(i18n.getLocale());

  React.useEffect(() => {
    const handleLocaleChange = (event: CustomEvent) => {
      setLocale(event.detail.locale);
    };

    window.addEventListener('localechange', handleLocaleChange as EventListener);
    return () => {
      window.removeEventListener('localechange', handleLocaleChange as EventListener);
    };
  }, []);

  return {
    t: (key: string, params?: Record<string, string | number>) => i18n.t(key, params),
    locale,
    setLocale: (newLocale: string) => i18n.setLocale(newLocale),
    supportedLocales: i18n.getSupportedLocales(),
  };
}

// Add React import for the hook
import React from 'react';
