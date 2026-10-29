.pragma library

// Apple Human Interface Guidelines palette. Every color in the UI comes
// from here (or from a QColor constant in ui/actions_ring_overlay.py that
// mirrors the accent) so the app reads as a native macOS utility in both
// appearances. The accent is the macOS selection blue (deeper than the iOS
// system blue, so filled chips and toggles read as native controls) and
// everything drawn on it uses onAccent. Semantic reds, greens and oranges
// are the HIG system colors. tests/test_theme.py pins the accents.
var radius = 10

// Brand-asset colors are intentionally theme-independent: the sidebar
// brand mark draws a pocket-sized echo of the Dock tile, so it must render
// identically under light and dark appearances.
var brandMarkBg = "#1d1d1f"
var brandMarkFg = "#ffffff"

function palette(isDark) {
    if (isDark) {
        return {
            bg: "#1c1c1e",           // systemBackground
            bgElevated: "#2c2c2e",   // secondarySystemBackground
            bgCard: "#2c2c2e",
            bgCardHover: "#3a3a3c",  // tertiarySystemBackground
            bgSidebar: "#161618",
            bgInput: "#1c1c1e",
            bgSubtle: "#232325",
            accent: "#3478f6",       // macOS control blue (dark)
            accentHover: "#4a8bf8",
            accentDim: "#1c2f4f",
            onAccent: "#ffffff",     // text and icons drawn on the accent
            textPrimary: "#f5f5f7",  // label
            textSecondary: "#a1a1a6",// secondaryLabel
            textDim: "#6e6e73",      // tertiaryLabel
            border: "#3a3a3c",       // separator
            danger: "#ff453a",       // systemRed (dark)
            dangerBg: "#3b1f1e",
            success: "#30d158",      // systemGreen (dark)
            warning: "#ff9f0a",      // systemOrange (dark)
            tooltipBg: "#3a3a3c",
            tooltipText: "#f5f5f7",
            brandMarkBg: brandMarkBg,
            brandMarkFg: brandMarkFg
        }
    }

    return {
        bg: "#f5f5f7",               // grouped background
        bgElevated: "#ffffff",
        bgCard: "#ffffff",
        bgCardHover: "#f2f2f7",      // secondarySystemGroupedBackground
        bgSidebar: "#ececf0",
        bgInput: "#ffffff",
        bgSubtle: "#f2f2f7",
        accent: "#0063e1",           // macOS selection blue (light)
        accentHover: "#1a6fe8",
        accentDim: "#e4eefc",
        onAccent: "#ffffff",         // text and icons drawn on the accent
        textPrimary: "#1d1d1f",      // label
        textSecondary: "#6e6e73",    // secondaryLabel
        textDim: "#86868b",          // tertiaryLabel
        border: "#d2d2d7",           // separator
        danger: "#ff3b30",           // systemRed
        dangerBg: "#ffe5e3",
        success: "#34c759",          // systemGreen
        warning: "#ff9500",          // systemOrange
        tooltipBg: "#1d1d1f",
        tooltipText: "#f5f5f7",
        brandMarkBg: brandMarkBg,
        brandMarkFg: brandMarkFg
    }
}
