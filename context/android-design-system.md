# Android Design System and Resource Migration

Last updated: 2026-07-21  
Status: Phase 4 shared component resources complete; no fonts or raster assets imported

## Purpose

Turn AppHear2's visual language into a versioned, reusable AppHear3 resource system without
overwriting runtime resources or propagating hardcoded text, colors, spacing, and obsolete controls.
Use this file for visual inconsistencies, resource collisions, and asset provenance questions.

## Scope and sources of truth

- UI reference resources:
  `D:/Programming/MOBILE APP/3.1 New Way/backup/AppHear2/app/src/main/res/`
- Target resources: `F:/ASL DATASET/5. Apphear3/android/app/src/main/res/`
- Screen mapping: [`android-screen-mapping.md`](android-screen-mapping.md)
- Architecture: [`android-ui-architecture.md`](android-ui-architecture.md)
- Migration gates: [`android-migration-plan.md`](android-migration-plan.md)

This file owns UI tokens and resource mapping only. Runtime numerical constraints remain in
[`runtime-constraints.md`](runtime-constraints.md).

## Verified reference visual language

### Color palette

| Existing AppHear2 name | Value | Observed role | Proposed semantic token |
|---|---:|---|---|
| `teal_primary` | `#2AA897` | primary brand/actions/highlight | `color_brand_primary` |
| `teal_light` | `#D6EDE8` | camera/feature background | `color_brand_surface` |
| `teal_card` | `#F4F8F7` | light card | `color_surface_tinted` |
| `beige` | `#FAEFD9` | loading/onboarding warmth | `color_surface_warm` |
| literal home background | `#F6F5EC` | home/profile background | `color_surface_app` |
| `coffee` / `start_color` | `#2C1810` | dark settings panel/primary dark button | `color_action_dark` |
| `dark_bg` | `#080810` | legacy sign-detect dark surface | verify before reuse |
| `sd_text_primary` | `#0D1B1E` | primary dark text | `color_text_primary` |
| `sd_text_secondary` | `#7A9A95` | secondary text | `color_text_secondary` |
| `status_green` | `#34C759` | ready/live | `color_status_ready` |
| `status_yellow` | `#FFCC00` | caution | `color_status_warning` |
| `status_red` | `#FF3B30` | error/stop | `color_status_error` |
| `stop_color` | `#FF4455` | stop/destructive action | `color_action_destructive` |
| `sign_cyan` | `#5CE1FF` | legacy recognition accent | verify/possibly exclude |

The palette values are verified references, not automatically approved contrast pairs. Before
finalization, measure WCAG contrast for text, icons, disabled states, status colors, and camera
overlays against real backgrounds.

### Typography

AppHear2 bundles Inter Regular, Italic, Semibold, Bold, ExtraBold, and Black under `res/font/`.
It also mixes resource fonts with `sans-serif`, `sans-serif-medium`, and `sans-serif-black`.

Proposed type roles:

| Role | Reference tendency | Proposed resource/style |
|---|---|---|
| Display/hero | Inter Black | `TextAppearance.AppHear.Display` |
| Screen title | Inter Black/ExtraBold | `TextAppearance.AppHear.Title` |
| Card title/action | Inter Bold/Semibold | `TextAppearance.AppHear.Headline` |
| Body | Inter Regular | `TextAppearance.AppHear.Body` |
| Label | Inter Semibold | `TextAppearance.AppHear.Label` |
| Diagnostics | monospace | `TextAppearance.AppHear.Diagnostics`, debug/runtime only |

Before importing fonts, verify license/provenance and decide whether all six files are necessary.
Avoid embedding both redundant system weights and multiple Inter weights without a measured need.

### Shape and component language

- Rounded pill buttons and chips.
- White or tinted rounded cards.
- Circular icon buttons and avatar containers.
- Teal live/status badges with dot indicators.
- Dark coffee settings panel on a warm background.
- Full-screen camera/avatar content with top/bottom gradients and a rounded bottom controls sheet.
- Mascot-led feature cards and onboarding imagery.

These patterns should become named styles/components; the old `bg_*` drawable names are references,
not the final public API.

## Token plan

Create these resource layers before screens:

```text
res/values/
  colors.xml          # semantic color tokens only
  dimens.xml          # spacing, radii, icon sizes, content widths
  typography.xml      # text appearances/font-family choices
  styles.xml          # component styles
  themes.xml          # app theme and Material token mapping
  strings.xml         # all user-facing copy
```

Recommended spacing scale: `4, 8, 12, 16, 20, 24, 32, 40, 48dp`. Existing values outside the scale
must be justified by a component/layout need. This is a proposed consolidation, not a claim that the
reference already follows the scale.

Recommended shape roles:

- `radius_small`: chips/status labels
- `radius_medium`: inputs/settings rows
- `radius_large`: cards/panels
- `radius_pill`: actions and segmented controls
- `radius_circle`: icon/avatar wrappers


### Implemented token ledger - 2026-07-21

| Target file | Added/changed | Source reference | Notes |
|---|---|---|---|
| `android/app/src/main/res/values/colors.xml` | Semantic brand, surface, text, action, divider, and status colors | AppHear2 `values/colors.xml` | Kept existing `black` and `white`; no old resource names imported. |
| `android/app/src/main/res/values/dimens.xml` | Spacing scale, radius scale, touch target, icon/avatar/common sizes | AppHear2 layout audit + migration plan | New file; no layout now consumes it. |
| `android/app/src/main/res/values/typography.xml` | Display/title/headline/body/label/diagnostic text appearances | AppHear2 Inter typography pattern | Uses Android system families only; Inter font import remains blocked by provenance approval. |
| `android/app/src/main/res/values/styles.xml` | Shared button, card, and status-chip style names | AppHear2 buttons/cards/chips | Conservative Material3 parents verified against local Material 1.14.0 resources. |
| `android/app/src/main/res/values/themes.xml` | Light theme maps Material color/system-bar/window tokens | AppHear2 warm neutral + teal theme | No launcher/layout/activity change. |
| `android/app/src/main/res/values-night/themes.xml` | Deliberate dark token mapping | Existing DayNight theme placeholder | Dark policy is basic token support, not final visual QA. |

No AppHear2 fonts, PNGs, GLB assets, old classifier files, old MediaPipe files, Java source, layouts, manifest entries, or Gradle dependencies were imported in this phase.

## Shared component plan

| Component | Reference resources | Target abstraction | Required states |
|---|---|---|---|
| Primary pill action | `bg_teal_pill_btn`, `btn_start_bg`, `bg_btn_dark_pill` | shared button style/layout | enabled, pressed, disabled, loading |
| Secondary/destructive action | `bg_chip_inactive`, `btn_stop_bg` | secondary/destructive styles | enabled, pressed, disabled |
| Circular icon action | `circle_btn_white`, `bg_btn_dark_circle`, `bg_circle_tan` | accessible icon button | selected/unselected/disabled |
| Status chip | `bg_status_pill`, `bg_live_badge*`, dots | semantic status component | ready, warming, low-FPS, error |
| Feature card | two `item_feature_card_*` layouts | data-driven shared card | detect, project, disabled/coming soon |
| Bottom controls sheet | recognition/text/conversation layouts | shared panel shell | collapsed, expanded, keyboard-safe |
| Settings row | `row_setting_*.xml` | label/description/value/switch variants | enabled, disabled, read-only |
| Empty/loading/error | scattered inline views | reusable state layouts | empty, loading, retryable error |

All touch targets must be at least 48dp, all icon-only controls need content descriptions, and status
must not be communicated by color alone.


### Implemented shared component ledger - 2026-07-21

| Target resource | Purpose | Notes |
|---|---|---|
| `component_status_chip.xml` + `apphear_status_chip_bg.xml` + `apphear_status_dot_ready.xml` | Semantic ready/live/status chip | Color is paired with text; future variants should swap both dot and label. |
| `component_feature_card.xml` | Reusable feature card shell with title, body, and action | Uses tokenized MaterialCardView and button styles; screen data binds later. |
| `component_settings_row.xml` | Settings row with title, description, and value slot | Switch/action variants can extend this pattern in screen phases. |
| `component_bottom_panel.xml` + panel/handle drawables | Shared rounded bottom controls panel | Intended for recognition/text/conversation controls after lifecycle work. |
| `component_loading_state.xml` | Reusable loading state | Uses platform ProgressBar and resource copy. |
| `component_empty_state.xml` | Reusable empty state | Honest placeholder for screens with no local data yet. |
| `component_error_state.xml` | Reusable retryable error state | Does not encode backend/runtime behavior. |
| `strings.xml` component copy | Shared labels, state copy, action text | Added as reusable defaults; screen-specific copy can override. |

No component contains camera, model, backend, WebView, auth, history, or recognition logic.
## Resource collision report

### Same relative path, different content

- `layout/activity_main.xml`
- `values/colors.xml`
- `values/strings.xml`
- `values/themes.xml`
- `values-night/themes.xml`
- `drawable/ic_launcher_background.xml`
- launcher bitmap files in mdpi/hdpi/xhdpi/xxhdpi/xxxhdpi

### Same relative path, byte-identical

- `drawable/ic_launcher_foreground.xml`
- `xml/backup_rules.xml`
- `xml/data_extraction_rules.xml`

Identical files still should not be bulk-copied; leave the target copy in place unless a documented
launcher update requires a change.

### Rename rules

- Screen layouts: `fragment_home.xml`, `activity_recognition.xml`,
  `fragment_text_to_asl.xml`, `fragment_profile.xml`, `fragment_settings.xml`.
- Shared views: prefix `component_` or `item_` with a precise role.
- Screen-specific drawables: prefix `home_`, `recognition_`, `translator_`, `profile_`, or
  `onboarding_`.
- Semantic shared drawables/styles: prefix `apphear_` or use style names, not appearance-only names
  such as `white_pill`.
- Imported raster assets retain neither ambiguous names (`week.png`, `hand.png`) nor density
  assumptions. Rename by meaning, e.g. `feature_detection_mascot`.

## Asset disposition

| Asset group | Reference location | Decision before import |
|---|---|---|
| Inter fonts | `res/font/inter_*.otf` | verify license; import selected weights only |
| App logo/launcher | drawable + mipmap sets | compare/approve as a distinct launcher task |
| Mascots/onboarding art | PNG drawables | verify provenance; optimize size; add descriptions |
| Navigation/icons | PNG + vector drawables | prefer vectors where faithful; rename and tint semantically |
| Shape/gradient drawables | `bg_*.xml`, `gradient_*.xml` | recreate against tokens; do not copy literals blindly |
| GLB ASL animations | `assets/asl_animations/*.glb` | inventory manifest/coverage/license/size before Text-to-ASL phase |
| `model_viewer.html` | assets | security/lifecycle review before WebView use |
| Old classifiers/labels | root assets | exclude |
| `face_landmarker.task` | root assets | exclude; face is forbidden by AppHear3 contract |
| Hand/pose `.task` files | root assets | do not import; AppHear3 canonical copies already exist |

## Localization and copy

The reference has only three string resources and hardcodes most visible copy in layouts/Java.
During migration:

- Move every user-visible string, content description, error, hint, and accessibility label to
  `strings.xml` before a screen is marked done.
- Keep developer diagnostics distinct from polished user copy.
- Do not expose raw gloss identifiers with numeric suffixes unless the product intentionally does.
- Use formatted resources for dynamic FPS, candidate confidence, names, and status messages.
- Plan plural resources for counts and history.

## Theme decisions

- Continue XML Views and Material 3; do not introduce Compose during the migration.
- Use a light-first brand theme based on warm neutral + teal; define a deliberate night policy
  rather than inheriting an incomplete DayNight theme.
- Camera/recognition overlays may use dark translucent surfaces independent of app light/dark theme.
- System bars, edge-to-edge behavior, insets, keyboard resizing, and contrast are defined once in
  theme/shell code rather than per screen.

## Verification checklist

- Resource merge/build succeeds with no duplicate names.
- No user-facing hardcoded text remains on the migrated screen.
- No literal color remains outside approved exceptional assets/gradients.
- Font fallback and missing-font behavior are checked.
- Screens render at small/large font scales and narrow/large phones.
- TalkBack order, descriptions, roles, and touch targets are checked.
- Light/night/system-bar behavior is intentional.
- Recognition overlay alignment is unchanged after restyling.
- Imported PNG/GLB assets have provenance and size recorded.

## Assumptions requiring confirmation

- Warm neutral + teal is the desired production palette.
- Inter is approved for redistribution.
- Mascot and ASL animation assets are approved and production-quality.
- A formal dark theme is desired; the reference night theme is incomplete.

## Decisions

- Tokenize before migrating screens.
- Never overwrite target resources by filename.
- Preserve recognition coordinate/overlay behavior; visual styling does not change analysis input.
- Exclude old model/landmarker assets regardless of their visual feature association.

## Known risks

- Raster art and six font weights increase APK size.
- Literal reference colors may fail contrast when reused in new component combinations.
- `activity_main.xml` collision can overwrite either home or recognition UI if names are not changed.
- Reference icons mix raster and vector styles and may look inconsistent when tinted/scaled.

## Current status

Phase 4 shared component resources are complete and build-verified. Fonts, raster art, GLB assets, screen visual migration, launcher switching, and recognition UI restyling remain not started.



## 2026-07-21 Home/nav UI reference correction resource import

Purpose: correct the visible Home/dashboard mismatch against `context/design/homapage.jpg` and AppHear2 `activity_main.xml`/feature-card/nav XML.

Imported selected non-conflicting AppHear2 resources into `android/app/src/main/res/`:

- Fonts: `font/inter_black.otf`, `font/inter_bold.otf`, `font/inter_regular.otf`, `font/inter_semibold.otf`.
- Home/nav raster assets: `drawable/account.png`, `drawable/mascot_detect.png`, `drawable/mascot_project.png`, `drawable/whitearrow.png`, `drawable/homes.png`, `drawable/user_images.png`, `drawable/wave_hand.png`, `drawable/users.png`.
- Home/nav drawables: `circle_avatar.xml`, `bg_status_pill.xml`, `dot_green.xml`, `bg_live_badge.xml`, `bg_live_badge_dark.xml`, `bg_btn_dark_pill.xml`, `bg_btn_dark_circle.xml`, `dot_active_pill.xml`, `dot_inactive_circle.xml`, `bg_nav_active_circle.xml`, `bg_nav_inactive_pill.xml`, `bg_chip_active.xml`, `bg_chip_inactive.xml`.

Decision: copied these names directly because pre-copy conflict checks showed they did not exist in AppHear3. Launcher assets and unrelated AppHear2 resources were not copied. Provenance/license and APK-size review remain open before release.

Related tracker: [`android-ui-reference-correction.md`](android-ui-reference-correction.md).
## 2026-07-21 Recognition UI reference correction resource import

Purpose: correct `RecognitionActivity` against the AppHear2 sign-detect visual reference without importing old recognition logic.

Imported selected non-conflicting AppHear2 resources into `android/app/src/main/res/drawable/`: `gradient_top.xml`, `gradient_bottom.xml`, `arrow.png`, `flip.png`, `circle_btn_white.xml`, `bg_landmark_toggle.xml`, `hand_recognition.png`, `btn_start_bg.xml`, `btn_stop_bg.xml`, `play.png`, `soundwaves.png`, `ic_conversation.xml`, `bar_track.xml`, `bar_fill.xml`, `bg_white_pill.xml`, `bg_detect_card.xml`, `ic_replay.xml`, `ic_volume.xml`, and `bg_glass_pill.xml`.

Decision: direct names were used only after conflict checks showed they did not exist in AppHear3. The AppHear2 face-landmark icon and old `LandmarkOverlayView` implementation were not imported. AppHear3 `OverlayView` and recognition binding IDs remain active.
## 2026-07-21 Text-to-ASL UI reference correction resource import

Purpose: correct `TextToAslFragment` against AppHear2 `activity_text_to_asl.xml` without importing avatar playback or speech behavior.

Imported selected non-conflicting AppHear2 resources into `android/app/src/main/res/drawable/`: `bg_circle_tan.xml`, `bg_toggle_container.xml`, `bg_toggle_active.xml`, `bg_toggle_inactive.xml`, and `ic_mic.xml`.

Decision: existing resources from prior Home/Recognition imports were reused (`gradient_top.xml`, `circle_btn_white.xml`, `arrow.png`, `ic_volume.xml`, `bg_glass_pill.xml`, `bg_white_pill.xml`, `btn_start_bg.xml`, `ic_replay.xml`, `ic_conversation.xml`). No WebView assets, GLB animation assets, speech/TTS resources, or old Java behavior were imported.
### 2026-07-22 Settings/Profile imported visual resources

- AppHear2 profile/settings drawables now used in AppHear3: `bg_profile_card_white.xml`, `bg_profile_avatar_teal.xml`, `bg_auth_input_large.xml`, `bg_settings_panel_coffee.xml`, `bg_setting_row.xml`, `bg_setting_value_pill.xml`, and `bg_teal_pill_btn.xml`.
- AppHear2 `row_setting_*.xml` layouts were imported as passive visual resources, but AppHear2-only/beta runtime rows are no longer included in visible Profile/Settings screens. Visible settings are limited to safe passive rows: account type, voice output, accessibility, privacy, and about.
- Existing semantic `apphear_*` settings components remain available for future refactors; do not delete until usage is audited.
- 2026-07-22 cleanup: removed visible AppHear2-only settings for duplicate suppression, hand-presence gate, face landmarks, beta detector/model/vocabulary controls, rotate/parallel/profiling dev toggles, and detection header from Profile/Settings layouts. Unused row resource files remain for later audited cleanup.
