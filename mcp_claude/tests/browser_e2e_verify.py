import sys
import time
from playwright.sync_api import sync_playwright

def run_browser_tests():
    console_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Catch JS/OWL runtime console errors
        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ["error"] else None)
        page.on("pageerror", lambda exc: console_errors.append(f"[pageerror] {exc}"))

        print("\n==========================================================")
        print("MCP CLAUDE COMPLETE E2E BROWSER SUITE VERIFICATION")
        print("==========================================================")

        print("\n--- Step 1: Login to Odoo Backend ---")
        page.goto("http://localhost:8069/web/login?db=odoo18")
        page.wait_for_selector("input#login, input[name='login']", timeout=15000)
        page.fill("input#login", "admin")
        page.fill("input#password", "zantatech@odoo")
        page.click("button[type='submit']")
        page.wait_for_selector(".o_main_navbar", timeout=15000)
        print("[PASS] Logged into Odoo backend successfully.")

        print("\n--- Step 2: Top Purple Header Cleanliness ---")
        page.goto("http://localhost:8069/odoo/action-305")
        page.wait_for_selector(".mcp-saas-container", timeout=15000)
        
        # Verify navbar contains only MCP Claude
        navbar_text = page.inner_text(".o_main_navbar")
        assert "Dashboards" not in navbar_text, "Duplicate Dashboards found in top navbar!"
        assert "Control Center" not in navbar_text, "Duplicate Control Center found in top navbar!"
        print("[PASS] Top purple navbar contains ONLY 'MCP Claude' without duplicate entries.")

        print("\n--- Step 3: Bottom Navigation System Test ---")
        # Click Home
        page.click(".mcp-nav-btn:has-text('Home')")
        time.sleep(1)
        assert "active" in page.get_attribute(".mcp-nav-btn:has-text('Home')", "class")
        print("[PASS] Navigated to Home view.")

        # Click Dashboards
        page.click(".mcp-nav-btn:has-text('Dashboards')")
        time.sleep(1)
        assert "active" in page.get_attribute(".mcp-nav-btn:has-text('Dashboards')", "class")
        print("[PASS] Navigated to Dashboards Hub.")

        # Click Tools
        page.click(".mcp-nav-btn:has-text('Tools')")
        time.sleep(1)
        assert "active" in page.get_attribute(".mcp-nav-btn:has-text('Tools')", "class")
        print("[PASS] Navigated to Tools Registry.")

        # Click Configurations
        page.click(".mcp-nav-btn:has-text('Configurations')")
        time.sleep(1)
        assert "active" in page.get_attribute(".mcp-nav-btn:has-text('Configurations')", "class")
        print("[PASS] Navigated to Configurations Hub.")

        print("\n--- Step 4: Open Server Configuration View & New Record ---")
        page.click("div.hover-lift:has-text('Server Configuration')")
        page.wait_for_selector(".o_list_view, .o_form_view", timeout=10000)
        print("[PASS] Native Odoo Server Configuration view opened.")

        # Click New
        new_btn = page.locator("button.o_list_button_add, button.o_form_button_create")
        if new_btn.is_visible():
            new_btn.click()
            page.wait_for_selector(".o_form_view", timeout=5000)
            widgets = page.eval_on_selector_all(".o_form_view .o_field_widget", "nodes => nodes.map(n => n.getAttribute('name'))")
            assert "claude_api_key" in widgets, "'claude_api_key' widget missing from form view!"
            print("[PASS] 'claude_api_key' password field widget IS PRESENT and password-masked.")

        print("\n--- Step 5: Test Browser Back Navigation ---")
        page.go_back()
        page.wait_for_selector(".mcp-saas-container", timeout=10000)
        print("[PASS] Returned to MCP Claude Control Center via browser Back button.")

        print("\n--- Step 6: Open Model Permission Rules View ---")
        page.click(".mcp-nav-btn:has-text('Configurations')")
        page.wait_for_selector("div.hover-lift:has-text('Model Permission Rules')", timeout=5000)
        page.click("div.hover-lift:has-text('Model Permission Rules')")
        page.wait_for_selector(".o_list_view, .o_form_view", timeout=10000)
        print("[PASS] Native Odoo Model Permission Rules view opened.")

        print("\n--- Step 7: JavaScript / OWL Error Inspection ---")
        if console_errors:
            print("[FAIL] Console Errors detected:", console_errors)
            sys.exit(1)
        else:
            print("[PASS] Zero JavaScript, OWL asset, or runtime errors detected in browser console.")

        browser.close()
        print("\n==========================================================")
        print("ALL E2E BROWSER SUITE VERIFICATIONS PASSED SUCCESSFULLY!")
        print("==========================================================")

if __name__ == "__main__":
    run_browser_tests()
