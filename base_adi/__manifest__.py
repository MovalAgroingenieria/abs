# 2024 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

{
    "name": "Administrative Divisions",
    "summary": "Management of a country's administrative divisions",
    "version": "16.0.1.0.0",
    "author": "Moval Agroingeniería",
    "license": "AGPL-3",
    "website": "https://moval.es",
    "category": "Hidden",
    "depends": [
        "base_gen",
        "base_gis",
    ],
    "data": [
        "views/res_region_views.xml",
        "views/res_province_views.xml",
        "views/res_municipality_views.xml",
        "views/res_place_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "base_adi/static/src/scss/base_adi.scss",
        ]
    },
    "installable": True,
    "application": False,
}
