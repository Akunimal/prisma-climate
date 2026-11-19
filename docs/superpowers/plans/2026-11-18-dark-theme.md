# Dark Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide full Material 3 Dark Theme support in the PRISMA Flutter app with persistent user preference and an AppBar toggle button.

**Architecture:** Extend `PrismaApp` state in `app/lib/src/app.dart` to support `themeMode` (`ThemeMode.system`, `light`, `dark`), persistent via `SharedPreferences` under key `prisma_theme_mode`. Add M3 `darkTheme` with seed `0xFF0B6B45` and `Brightness.dark`. Add an interactive toggle button in `HomeShell` app bar actions.

**Tech Stack:** Flutter / Dart, Material 3, `shared_preferences`.

**Spec:** [docs/ROADMAP.md#L91](file:///d:/WORK/Climate%20Prediction/docs/ROADMAP.md#L91) (Candidate: Dark theme).

## Global Constraints

- Do not modify `.arb` files or add new localization keys unless added to all 10 locales with exact schema matching and non-identical values per `app/test/l10n_test.dart`. Use standard semantic/tooltip attributes or icons.
- M3 theme seed color remains `0xFF0B6B45` for both light and dark palettes.
- All existing 95 Flutter tests must continue to pass cleanly.

## Review Focus

1. **Preference Persistence**: App must correctly remember user's selected mode (`light` or `dark`) across page reloads.
2. **Initial / System Fallback**: If no preference is stored, app defaults to system brightness (`ThemeMode.system`).
3. **Contrast on Canvas**: `ForecastBandChart` CustomPainter must render text, grid lines, and percentile bands legibly against dark backgrounds without clipping.
4. **Model Colors**: Both `ecmwf_ifs025` and `gfs_seamless` lines in `modelColor()` must have sufficient contrast on dark surface.
5. **No regressions in layout/screen tests**: Existing widget tests in `screens_test.dart` must pass unchanged or with minimal required parameter additions.

---

### Task 1: Theme State, Dark ThemeData, and Persistence in `PrismaApp`

**Files:**
- Modify: `app/lib/src/app.dart:30-80`
- Test: `app/test/theme_test.dart`

**Steps:**
- [x] Add `_themePrefsKey = 'prisma_theme_mode'` and `_themeMode` state to `_PrismaAppState`.
- [x] Implement `_restoreThemeMode()` loading `'prisma_theme_mode'` (`'system'`, `'light'`, `'dark'`) defaulting to `ThemeMode.system`.
- [x] Implement `_pickThemeMode(ThemeMode mode)` setting state and saving to `SharedPreferences`.
- [x] Define `darkTheme` with `ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF0B6B45), brightness: Brightness.dark))` and set `themeMode: _themeMode` in `MaterialApp`.
- [x] Pass `currentThemeMode` and `onThemeModePicked` to `HomeShell`.

---

### Task 2: AppBar Theme Toggle Button in `HomeShell`

**Files:**
- Modify: `app/lib/src/app.dart:88-160`

**Steps:**
- [x] Add `onThemeModePicked` and `currentThemeMode` fields to `HomeShell`.
- [x] In `_appBarActions`, add an `IconButton` before `LanguageMenu`:
  - Key: `const ValueKey('theme_toggle_button')`.
  - Icon: `Icons.light_mode` when dark, `Icons.dark_mode` when light.
  - Tooltip: `'Toggle dark theme'`.
  - `onPressed`: toggles between `ThemeMode.light` and `ThemeMode.dark`.

---

### Task 3: Unit and Widget Tests

**Files:**
- Create: `app/test/theme_test.dart`

**Steps:**
- [x] Write widget tests for:
  - Defaulting to system/light theme.
  - Tapping theme toggle changes brightness from light to dark.
  - Selecting theme mode persists value in `SharedPreferences`.
- [x] Run `cd app; rtk flutter test test/theme_test.dart` to verify new tests pass.
- [x] Run full test suite `cd app; rtk flutter test` to ensure all 95+ tests pass with zero regressions.

---

### Task 4: Documentation & Roadmap Update

**Files:**
- Modify: `docs/ROADMAP.md:85-92`

**Steps:**
- [x] Update `docs/ROADMAP.md` moving "Dark theme" from Candidates to completed Phase 2 deliverable / shipped feature.
- [x] Run `rtk git status` and verify workspace is clean and ready.
