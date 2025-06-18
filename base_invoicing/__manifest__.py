# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

{
    'name': 'Massive Invoicing',
    'summary': 'Massive invoicing based on billing sets',
    'version': '16.0.1.0.0',
    'category': 'Accounting/Accounting',
    'website': 'https://www.moval.es',
    'author': 'Moval Agroingeniería',
    'license': 'AGPL-3',
    'application': False,
    'installable': True,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'depends': [
        'product',
        'analytic',
        'portal',
        'account',
        'base_gen',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/product_category_data.xml',
        'wizards/wizard_select_field_views.xml',
        'views/base_invoicing_menus.xml',
        'views/res_config_settings_views.xml',
        'views/account_invoiceset_views.xml',
        'views/account_move_views.xml',
        'views/account_move_line_views.xml',
        'views/product_category_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'base_invoicing/static/src/scss/base_invoicing.scss',
        ],
    },
}
