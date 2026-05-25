.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

========================
Administrative Divisions
========================

**Table of contents**

.. contents::
   :local:

Description
===========

Localization based on a hierarchical structure of administrative territories.

This module provides basic models to manage administrative divisions,
without enforcing menus or access rules by default.

Functionality
=============

* Management of regions.
* Management of the provinces of a region.
* Management of the municipalities of a province.
* Management of the places of a municipality.

Usage
=====

To use this module, it is necessary to:

* Create menu items mapped to the appropriate action windows.
* Assign user permissions using ``ir.model.access.csv``.

The available action windows are:

* ``base_adi.res_admregion_action`` for regions.
* ``base_adi.res_province_action`` for provinces.
* ``base_adi.res_municipality_action`` for municipalities.
* ``base_adi.res_place_action`` for places.

Credits
=======

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
* Jorge Vera <jvera@movalol.es>
* César Andrés <candres@moval.es>

Maintainer
----------

.. image:: https://raw.githubusercontent.com/MovalAgroingenieria/public-assets/master/logos/logo_moval_small.png
   :target: https://moval.es
   :alt: Moval Agroingeniería

This module is maintained by Moval Agroingeniería.
