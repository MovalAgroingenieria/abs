.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.png
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

=================
Massive Invoicing
=================

**Table of contents**

.. contents::
   :local:

Description
===========

This module provides massive invoicing functionality based on invoice sets. It allows generating multiple customer invoices in a single operation, using quantities obtained from configurable billable item models linked to partners.

Main features:

* **Invoice sets**: Create invoice sets with a description, dates, and payment terms.
* **Product links**: Associate products with billable models and quantity fields per product category.
* **Billable items**: Any model inheriting ``account.billable.item`` (e.g. ``res.partner``, custom models) can be used as a source for billable quantities.
* **Selectable items**: Assisted selection of billable items through hybrid views with configurable auxiliary columns.
* **Background calculation**: Optional generation of invoices in the background with progress tracking.
* **Comment templates**: Integration with ``account_comment_template`` for partner-specific comments on invoices.

Installation
============

1. Install the module dependencies: ``account``, ``account_comment_template``, ``analytic``, ``portal``, ``product``, ``base_gen``.
2. Install the ``base_invoicing`` module from the Apps menu or via command line.

Configuration
=============

* Go to **Invoicing > Configuration > Settings** and configure:
  * **Invoice batch size for progress commits**: Number of invoices per batch when running in background (higher = faster, less frequent progress updates).
  * **Run invoice set calculation in background**: Enable to allow interruption of long calculations.
* **Product categories** (Invoicing): Extend product categories with a billable model, quantity field, grouping, and auxiliary columns for the selectable items list.

Usage
=====

1. Create an **invoice set** (Invoicing > Massive Invoicing > Invoice Sets).
2. Add **product links** with products, quantities, and optionally configure billable item selection (domain, auxiliary columns).
3. Use **Configure fields** to define which columns appear in the selectable items list.
4. Load and display selectable items, then select/deselect the records to invoice.
5. Click **Calculate** to generate draft invoices. Optionally run in background.
6. Validate invoices from the invoice set view or from the Invoices submenu.

Dependencies
============

* ``account``
* ``account_comment_template``
* ``analytic``
* ``portal``
* ``product``
* ``base_gen``

Credits
=======

* Moval Agroingeniería S.L.

Contributors
------------

* Guillermo Amante <gamante@moval.es>
* Samuel Fernández <sfernandez@moval.es>
* Alberto Hernández <ahernandez@moval.es>
* Eduardo Iniesta <einiesta@moval.es>
* Jesús Martínez <jmartinez@moval.es>
* Miguel Mora <mmora@moval.es>
* Miguel Ángel Rodríguez <marodriguez@moval.es>
* Juanu Sandoval <jsandoval@moval.es>
* Salvador Sánchez <ssanchez@moval.es>
* Jorge Vera <jvera@moval.es>
* César Andrés <candres@moval.es>

Maintainer
----------

.. image:: https://services.moval.es/static/images/logo_moval_small.png
   :target: https://www.moval.es
   :alt: Moval Agroingeniería

This module is maintained by Moval Agroingeniería.
