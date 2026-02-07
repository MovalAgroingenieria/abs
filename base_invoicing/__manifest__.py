# Copyright 2025 Moval Agroingeniería
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)
# pylint: disable=duplicate-code
{
    "name": "Massive Invoicing",
    "summary": "Massive invoicing based on invoice sets",
    "version": "18.0.1.0.1",
    "category": "Accounting/Accounting",
    "website": "https://www.moval.es",
    "author": "Moval Agroingeniería",
    "license": "AGPL-3",
    "depends": [
        "account",
        "account_comment_template",
        "analytic",
        "portal",
        "product",
        "base_gen",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "data/product_category_data.xml",
        "data/base_invoicing_cron.xml",
        "wizards/wizard_config_billable_item_fields_views.xml",
        "wizards/wizard_confirm_productlink_action_views.xml",
        "views/base_invoicing_menus.xml",
        "views/res_config_settings_views.xml",
        "views/account_invoiceset_views.xml",
        "views/account_move_views.xml",
        "views/account_move_line_views.xml",
        "views/product_category_views.xml",
        "views/product_category_invoicing_views.xml",
        "views/account_selectable_item_views.xml",
        "views/product_views.xml",
        "views/account_portal_templates.xml",
    ],

    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "assets": {
        "web.assets_backend": [
            "base_invoicing/static/src/js/productlink_section_and_note_list.js",
            "base_invoicing/static/src/scss/base_invoicing.scss",
            "base_invoicing/static/src/xml/button_back.xml",
            "base_invoicing/static/src/js/massive_invoicing_list_renderer.js",
            "base_invoicing/static/src/js/selectable_item_hybrid_list.esm.js",
            "base_invoicing/static/src/js/massive_invoicing_search_model.js",
            "base_invoicing/static/src/js/massive_invoicing_form_controller.js",
            "base_invoicing/static/lib/base_invoicing_iconset/iconset.css",
        ],
        "web.assets_frontend": [
            "base_invoicing/static/lib/base_invoicing_iconset/iconset.css",
        ],
        "web.report_assets_common": [
            "base_invoicing/static/lib/base_invoicing_iconset/iconset.css",
        ],
    },
}
