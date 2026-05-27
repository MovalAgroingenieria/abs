/** @odoo-module **/

import {
    SectionAndNoteListRenderer,
    sectionAndNoteFieldOne2Many,
} from "@account/components/section_and_note_fields_backend/section_and_note_fields_backend";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { registry } from "@web/core/registry";

/**
 * List renderer for productlink lines with section/note support.
 * Uses line_name as the title field (instead of "name" like account.move.line).
 *
 * Design notes:
 * - line_name is excluded from the header (not in this.columns) to avoid an
 *   extra empty column for product rows.
 * - For section/note rows, getColumns() manually injects line_name (from
 *   this.allColumns) with the correct colspan.
 * - focusToName and focusCell are overridden to directly target the DOM cell
 *   because line_name is not in this.columns.
 */
export class ProductlinkSectionAndNoteListRenderer extends SectionAndNoteListRenderer {
    setup() {
        super.setup();
        this.titleField = "line_name";
    }

    /**
     * Exclude line_name from the active columns so it does not appear as a
     * column header for product rows.  It is injected manually in
     * getColumns() for section/note rows.
     */
    getActiveColumns(list) {
        return super
            .getActiveColumns(list)
            .filter((col) => col.name !== this.titleField);
    }

    /**
     * Section/note rows: return [handle, line_name(colspan=all-other-cols)].
     * Product rows: return the normal active columns (no line_name column).
     */
    getColumns(record) {
        if (this.isSectionOrNote(record)) {
            const titleCol = this.allColumns.find((c) => c.name === this.titleField);
            if (!titleCol) {
                return super.getColumns(record);
            }
            const handleCols = this.columns.filter((c) => c.widget === "handle");
            const colspan = this.columns.length - handleCols.length;
            return [...handleCols, { ...titleCol, colspan }];
        }
        return super.getColumns(record);
    }

    /**
     * Focus the title-field cell directly via DOM query when a new
     * section/note row is created, because line_name is not in this.columns
     * and the inherited focusCell() lookup would silently fail.
     */
    focusToName(editRec) {
        if (editRec && editRec.isNew && this.isSectionOrNote(editRec)) {
            const cell = this.tableRef.el?.querySelector(
                `.o_selected_row td[name='${this.titleField}']`
            );
            const input = cell && cell.querySelector("input, textarea");
            if (input) {
                input.focus();
            }
        }
    }

    /**
     * For section/note rows, bypass the this.columns lookup in the parent
     * focusCell (which fails since line_name is not in this.columns) and
     * focus the title-field DOM cell directly.
     */
    focusCell(column, forward = true) {
        if (this.editedRecord && this.isSectionOrNote(this.editedRecord)) {
            const cell = this.tableRef.el?.querySelector(
                `.o_selected_row td[name='${this.titleField}']`
            );
            const input = cell && cell.querySelector("input, textarea");
            if (input) {
                input.focus();
                this.lastEditedCell = {
                    column: this.allColumns.find((c) => c.name === this.titleField),
                    record: this.editedRecord,
                };
                return;
            }
        }
        super.focusCell(column, forward);
    }
}

export class ProductlinkSectionAndNoteOne2Many extends X2ManyField {
    static components = {
        ...X2ManyField.components,
        ListRenderer: ProductlinkSectionAndNoteListRenderer,
    };
}

export const productlinkSectionAndNoteOne2Many = {
    ...x2ManyField,
    component: ProductlinkSectionAndNoteOne2Many,
    additionalClasses: [
        ...(sectionAndNoteFieldOne2Many.additionalClasses || []),
        "o_field_one2many",
    ],
};

registry
    .category("fields")
    .add("productlink_section_and_note_one2many", productlinkSectionAndNoteOne2Many);
