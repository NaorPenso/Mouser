pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import "Theme.js" as Theme

/*  Accordion picker for a button's double-press action ("<button>_double").

    Collapsed it is one row: "Double press" and the current action. Expanded
    it lists the action categories as accordions of the same chips the main
    picker uses; the category holding the current action starts open.      */

Column {
    id: picker
    readonly property var theme: Theme.palette(uiState.darkMode)
    property var s: lm.strings

    property string actionId: "none"
    property bool expanded: false

    signal picked(string aid)
    signal customRequested()

    readonly property bool isCustom: actionId.indexOf("custom:") === 0
                                     || actionId.indexOf("hold:") === 0
    readonly property string currentLabel: actionId === "none"
                                           ? (s["mouse.double_press_off"] || "Off")
                                           : backend.actionLabelFor(actionId)

    function categoryHolds(category, aid) {
        var actions = category.actions || []
        for (var i = 0; i < actions.length; i++) {
            var id = actions[i].id
            if (id === aid || (id === "__custom__" && picker.isCustom))
                return true
        }
        return false
    }

    spacing: 8

    // ── Header: the collapsed accordion row ─────────────────────
    Rectangle {
        id: header
        objectName: "doublePressHeader"
        width: picker.width
        height: 44
        radius: 10
        color: headerMouse.containsMouse ? picker.theme.bgCardHover : picker.theme.bgSubtle
        border.width: 1
        border.color: picker.expanded ? picker.theme.accent : picker.theme.border

        Accessible.role: Accessible.Button
        Accessible.name: (picker.s["mouse.double_press"] || "Double press")
                         + ": " + picker.currentLabel

        Behavior on color { ColorAnimation { duration: 120 } }

        RowLayout {
            anchors { fill: parent; leftMargin: 14; rightMargin: 14 }
            spacing: 10

            Text {
                text: picker.s["mouse.double_press"] || "Double press"
                font { family: uiState.fontFamily; pixelSize: 12; bold: true }
                color: picker.theme.textPrimary
            }

            Text {
                objectName: "doublePressCurrent"
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignRight
                elide: Text.ElideRight
                text: picker.currentLabel
                font { family: uiState.fontFamily; pixelSize: 12 }
                color: picker.actionId === "none"
                       ? picker.theme.textDim : picker.theme.accent
            }

            Text {
                text: "›"
                rotation: picker.expanded ? 90 : 0
                font { family: uiState.fontFamily; pixelSize: 18 }
                color: picker.theme.textSecondary
                Behavior on rotation { NumberAnimation { duration: 150 } }
            }
        }

        MouseArea {
            id: headerMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: picker.expanded = !picker.expanded
        }
    }

    // ── Body: hint plus one accordion per action category ───────
    Column {
        objectName: "doublePressBody"
        width: picker.width
        spacing: 6
        visible: picker.expanded

        Text {
            width: parent.width
            wrapMode: Text.WordWrap
            bottomPadding: 4
            text: (picker.s["mouse.double_press_hint"] || "")
                  + " " + (backend.doublePressMode === "wait"
                           ? picker.s["mouse.double_press_mode_wait"]
                           : picker.s["mouse.double_press_mode_instant"])
                  + " · " + backend.doublePressWindowMs + " ms."
            font { family: uiState.fontFamily; pixelSize: 12 }
            color: picker.theme.textSecondary
        }

        Repeater {
            model: backend.actionCategories

            delegate: Column {
                id: group
                required property var modelData
                readonly property bool holdsCurrent:
                    picker.categoryHolds(modelData, picker.actionId)
                property bool open: holdsCurrent

                width: picker.width
                spacing: 6

                Rectangle {
                    objectName: "doublePressCategory_" + group.modelData.category
                    width: parent.width
                    height: 34
                    radius: 8
                    color: groupMouse.containsMouse
                           ? picker.theme.bgCardHover : "transparent"

                    Accessible.role: Accessible.Button
                    Accessible.name: group.modelData.category

                    RowLayout {
                        anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
                        spacing: 8

                        Text {
                            text: "›"
                            rotation: group.open ? 90 : 0
                            font { family: uiState.fontFamily; pixelSize: 15 }
                            color: picker.theme.textDim
                            Behavior on rotation { NumberAnimation { duration: 150 } }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: { var _lang = lm.strings; return lm.trCategory(group.modelData.category) }
                            font { family: uiState.fontFamily; pixelSize: 11;
                                   capitalization: Font.AllUppercase; letterSpacing: 1 }
                            color: group.holdsCurrent
                                   ? picker.theme.accent : picker.theme.textDim
                        }

                        Rectangle {
                            visible: group.holdsCurrent
                            width: 6; height: 6; radius: 3
                            color: picker.theme.accent
                        }
                    }

                    MouseArea {
                        id: groupMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: group.open = !group.open
                    }
                }

                Flow {
                    width: parent.width
                    leftPadding: 10
                    spacing: 8
                    visible: group.open

                    Repeater {
                        model: group.modelData.actions
                        delegate: ActionChip {
                            required property var modelData
                            objectName: "doublePressChip_" + modelData.id
                            actionId: modelData.id
                            actionLabel: modelData.id === "__custom__" && picker.isCustom
                                         ? picker.currentLabel
                                         : (lm.strings, lm.trAction(modelData.label))
                            isCurrent: modelData.id === "__custom__"
                                       ? picker.isCustom
                                       : modelData.id === picker.actionId
                            onPicked: function(aid) {
                                if (aid === "__custom__")
                                    picker.customRequested()
                                else
                                    picker.picked(aid)
                            }
                        }
                    }
                }
            }
        }
    }
}
