# 2026 Moval Agroingenieria
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

{
    "name": "Base GIS Viewer",
    "summary": "Shared GIS viewer configuration and cartographic services",
    "version": "18.0.1.0.0",
    "author": "Moval Agroingenieria",
    "license": "AGPL-3",
    "website": "https://moval.es",
    "category": "Hidden",
    "depends": [
        "base_setup",
        "base_gis",
    ],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "external_dependencies": {
        "python": ["pycryptodome"],
    },
    "installable": True,
}
