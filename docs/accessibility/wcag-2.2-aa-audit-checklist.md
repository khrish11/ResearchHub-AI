# WCAG 2.2 AA Audit Checklist

## Automated Audit
1. Run `npm run build` in `frontend/`.
2. Run `npm run a11y:ci` in `frontend/`.
3. Archive audit output with release artifacts.

## Manual Keyboard Checks
1. Verify all interactive controls are reachable with `Tab`.
2. Verify visible focus indicator on each focusable element.
3. Verify modal/dialog escape and focus trap behavior.
4. Verify no keyboard traps in search/import/filter flow.

## Screen Reader Checks
1. NVDA (Windows) on login, search, workspace, data rights pages.
2. Verify headings hierarchy and landmark regions.
3. Verify all form controls have label associations.
4. Verify status updates use `aria-live` where required.

## Visual/Contrast Checks
1. Text contrast meets AA minimum (4.5:1 normal text, 3:1 large text).
2. Color is not the only means of conveying status.
3. Zoom to 200% and verify layout/functionality.
4. Verify mobile viewport behavior at 320px width.

## Release Gate
- No unresolved `critical` accessibility issues.
- `serious` issues require explicit waiver + target fix date.
