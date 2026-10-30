import { test, expect } from '@playwright/test';

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/login');
    await page.getByLabel(/email/i).fill('demo@coredent.com');
    await page.getByLabel(/password/i).fill('demo123');
    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('should navigate to patients page', async ({ page }) => {
    await page.getByRole('link', { name: /patients/i }).click();
    await expect(page).toHaveURL(/\/patients/);
    await expect(page.getByRole('heading', { name: /patients/i })).toBeVisible();
  });

  test('should navigate to schedule page', async ({ page }) => {
    await page.getByRole('link', { name: /schedule/i }).click();
    await expect(page).toHaveURL(/\/schedule/);
  });

  test('should navigate to billing page', async ({ page }) => {
    await page.getByRole('link', { name: /billing/i }).click();
    await expect(page).toHaveURL(/\/billing/);
  });

  test('should show breadcrumbs on navigation', async ({ page }) => {
    await page.getByRole('link', { name: /patients/i }).click();
    
    // Check breadcrumbs
    await expect(page.getByRole('navigation')).toContainText('Patients');
  });

  test('should collapse sidebar on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    
    // Sidebar should be hidden initially
    const sidebar = page.locator('aside').first();
    await expect(sidebar).not.toBeVisible();
    
    // Open sidebar
    await page.getByRole('button', { name: /menu/i }).click();
    await expect(sidebar).toBeVisible();
  });
});
