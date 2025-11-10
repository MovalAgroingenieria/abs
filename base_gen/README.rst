.. image:: https://img.shields.io/badge/license-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

===================
Base General Module
===================

**Table of contents**

.. contents::
   :local:

Overview
========

This module provides **general-purpose utilities** to be reused across custom developments and company-specific addons.

Key features
------------

* Base model for master data (code + description pattern).
* Common reusable helpers for logging, formatting, metadata, and image utilities.
* Predefined constants and safe coding conventions for consistency.
* Designed for Odoo 18.0 with full Python 3.12 compatibility.

Installation
============

1. Clone or add this module to your Odoo addons path.
2. Update your Odoo configuration file to include the path.
3. Restart the Odoo service and update the app list.
4. Install **Base General** via *Apps → Update Apps List*.

Usage
=====

After installation:

* Developers can inherit from the `simple.model` abstract model to create master tables.
* Utility mixins are available under `common.*` (for example, `common.log`, `common.format`).
* Functions are fully compatible with the new Odoo 18.0 ORM and API decorators.

Example:

.. code-block:: python

   from odoo import models, fields

   class ProductCategory(models.Model):
       _name = "my.product.category"
       _inherit = "simple.model"

       extra_field = fields.Char("Extra Info")

Credits
=======

Authors
-------

* Moval Agroingeniería S.L.

Contributors
------------

* Samuel Fernández <sfernandez@moval.es>
* Alberto Hernández <ahernandez@moval.es>
* Eduardo Iniesta <einiesta@moval.es>
* Jesús Martínez <jmartinez@moval.es>
* Miguel Mora <mmora@moval.es>
* Miguel Ángel Rodríguez <marodriguez@moval.es>
* Juanu Sandoval <jsandoval@moval.es>
* Salvador Sánchez <ssanchez@moval.es>
* Jorge Vera <jvera@moval.es>

Maintainer
----------

.. image:: https://services.moval.es/static/images/logo_moval_small.png
   :target: https://www.moval.es
   :alt: Moval Agroingeniería

This module is maintained by **Moval Agroingeniería S.L.**

If you need support or want to contribute improvements, please contact us via our official website.
