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
 */
export class ProductlinkSectionAndNoteListRenderer extends SectionAndNoteListRenderer {
    setup() {
        super.setup();
        this.titleField = "line_name";
    }

    getCellClass(column, record) {
        let classNames = super.getCellClass(column, record);
        // Hide line_name cell for product lines (only relevant for section/note)
        if (
            !this.isSectionOrNote(record) &&
            column.name === this.titleField
        ) {
            classNames = `${classNames} o_hidden`;
        }
        return classNames;
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
