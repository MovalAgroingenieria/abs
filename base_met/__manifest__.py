# 2026 Moval Agroingenieria
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

{
    "name": "Base Metrology",
    "summary": "Abstract models for generic measurement data acquisition",
    "version": "18.0.1.0.0",
    "author": "Moval Agroingenieria",
    "license": "AGPL-3",
    "category": "Hidden",
    "depends": [
        "base_gen",
        "uom",
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "assets": {
        "web.assets_backend": [
            "base_met/static/lib/met_iconset/iconset.css",
        ],
        "web.assets_frontend": [
            "base_met/static/lib/met_invoicing_iconset/iconset.css",
        ],
        "web.report_assets_common": [
            "base_met/static/lib/met_iconset/iconset.css",
        ],
    },
}
