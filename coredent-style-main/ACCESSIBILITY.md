# Accessibility Guidelines

CoreDent is committed to providing an accessible experience for all users, including those with disabilities.

## WCAG Compliance

We strive to meet WCAG 2.1 Level AA standards. This includes:

- **Perceivable**: Information and UI components must be presentable to users in ways they can perceive
- **Operable**: UI components and navigation must be operable
- **Understandable**: Information and UI operation must be understandable
- **Robust**: Content must be robust enough to be interpreted by assistive technologies

## Keyboard Navigation

All interactive elements are keyboard accessible:

- **Tab**: Navigate forward through interactive elements
- **Shift + Tab**: Navigate backward
- **Enter/Space**: Activate buttons and links
- **Arrow Keys**: Navigate within components (menus, tabs, etc.)
- **Escape**: Close dialogs and menus
- **Home/End**: Jump to first/last item in lists

### Skip Links

A "Skip to main content" link appears when you press Tab on any page, allowing keyboard users to bypass navigation.

## Screen Reader Support

The application is tested with:
- NVDA (Windows)
- JAWS (Windows)
- VoiceOver (macOS/iOS)
- TalkBack (Android)

### ARIA Labels

All interactive elements have appropriate ARIA labels:
- Buttons describe their action
- Form inputs have associated labels
- Status messages use `aria-live` regions
- Dialogs use `role="dialog"` and `aria-modal="true"`

## Visual Accessibility

### Color Contrast

All text meets WCAG AA contrast requirements:
- Normal text: 4.5:1 minimum
- Large text (18pt+): 3:1 minimum
- UI components: 3:1 minimum

### Focus Indicators

All interactive elements have visible focus indicators with sufficient contrast.

### Text Sizing

- Base font size: 16px
- All text can be resized up to 200% without loss of functionality
- No horizontal scrolling at 320px viewport width

## Forms

- All form fields have visible labels
- Required fields are clearly marked
- Error messages are descriptive and associated with fields
- Form validation provides clear feedback

## Images and Icons

- Decorative images use `aria-hidden="true"`
- Informative images have descriptive alt text
- Icons paired with text use `aria-hidden="true"`
- Icon-only buttons have `aria-label`

## Modals and Dialogs

- Focus is trapped within open modals
- Focus returns to trigger element on close
- Escape key closes modals
- Background content is inert (`aria-hidden="true"`)

## Tables

- Data tables use proper semantic markup
- Headers are associated with data cells
- Complex tables include captions and summaries

## Testing

### Automated Testing

We use:
- axe-core for automated accessibility testing
- ESLint plugin for JSX accessibility
- Lighthouse accessibility audits

### Manual Testing

Regular testing includes:
- Keyboard-only navigation
- Screen reader testing
- Color contrast verification
- Zoom and text resize testing

## Known Issues

Currently tracked accessibility issues:
- [ ] None

## Reporting Issues

If you encounter accessibility barriers, please:
1. Email: accessibility@coredent.com
2. Include:
   - Description of the issue
   - Page/feature affected
   - Assistive technology used (if applicable)
   - Browser and OS

We aim to respond within 2 business days.

## Resources

- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/)
- [WebAIM Resources](https://webaim.org/resources/)

## Continuous Improvement

We regularly:
- Audit new features for accessibility
- Update components based on user feedback
- Train developers on accessibility best practices
- Monitor assistive technology compatibility

---

Last updated: February 2026
