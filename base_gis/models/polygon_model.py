# 2024 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import base64
import io
import re
import requests


from PIL import Image

from odoo import models, fields, api


class PolygonModel(models.AbstractModel):
    _name = 'polygon.model'
    _description = 'Polygon Model'

    # Default size for WMS images.
    NORMAL_SIZE = 512

    # Timeout for getmap requests.
    OGC_TIMEOUT = 5

    # Linked GIS table ("wua_gis_parcel", for example).
    _gis_table = ''

    # "geom" field.
    _geom_field = 'geom'

    # Field for link.
    _link_field = 'name'

    mapped_to_polygon = fields.Boolean(
        string='Mapped to polygon',
        compute='_compute_mapped_to_polygon',
        search='_search_mapped_to_polygon',)

    geom_ewkt = fields.Char(
        string='EWKT Geometry',
        compute='_compute_geom_ewkt',)

    oriented_envelope_ewkt = fields.Char(
        string='EWKT Geometry for oriented envelope',
        compute='_compute_oriented_envelope_ewkt',)

    area_gis = fields.Integer(
        string='GIS Area (m²)',
        compute='_compute_area_gis',)

    perimeter_gis = fields.Integer(
        string='GIS Perimeter (m)',
        compute='_compute_perimeter_gis',)

    centroid_ewkt = fields.Char(
        string='EWKT Centroid',
        compute='_compute_centroid_ewkt',)

    def _compute_mapped_to_polygon(self):
        geom_ok = self._geom_ok()
        for record in self:
            mapped_to_polygon = False
            if geom_ok:
                self.env.cr.execute("""
                    SELECT """ + self._link_field + """
                    FROM """ + self._gis_table + """
                    WHERE """ + self._link_field + """='""" + record.name + """'
                    """)
                query_results = self.env.cr.dictfetchall()
                if (query_results and
                   query_results[0].get(self._link_field) is not None):
                    mapped_to_polygon = True
            record.mapped_to_polygon = mapped_to_polygon

    def _search_mapped_to_polygon(self, operator, value):
        record_ids = []
        operator_of_filter = 'in'
        mapped_to_polygon = ((operator == '=' and value) or
                             (operator == '!=' and not value))
        geom_ok = self._geom_ok()
        if geom_ok:
            table = self._name.replace('.', '_')
            sql_statement = \
                'SELECT t.id FROM ' + table + ' t ' + \
                'INNER JOIN ' + self._gis_table + ' gt ' + \
                'ON t.name = gt.' + self._link_field
            if not mapped_to_polygon:
                sql_statement = \
                    'SELECT t.id FROM ' + table + ' t ' + \
                    'LEFT JOIN ' + self._gis_table + ' gt ' + \
                    'ON t.name = gt.' + self._link_field + ' ' + \
                    'WHERE gt.gid IS NULL'
            self.env.cr.execute(sql_statement)
            sql_resp = self.env.cr.fetchall()
            if sql_resp:
                for item in sql_resp:
                    record_ids.append(item[0])
        return [('id', operator_of_filter, record_ids)]

    def _compute_geom_ewkt(self):
        geom_ok = self._geom_ok()
        for record in self:
            geom_ewkt = ''
            if geom_ok:
                self.env.cr.execute("""
                    SELECT postgis.st_asewkt(""" + self._geom_field + """)
                    FROM """ + self._gis_table + """
                    WHERE """ + self._link_field + """
                    ='""" + record.name + """'""")
                query_results = self.env.cr.dictfetchall()
                if (query_results and
                   query_results[0].get('st_asewkt') is not None):
                    geom_ewkt = query_results[0].get('st_asewkt')
            record.geom_ewkt = geom_ewkt

    def _compute_oriented_envelope_ewkt(self):
        geom_ok = self._geom_ok()
        for record in self:
            oriented_envelope_ewkt = ''
            if geom_ok:
                self.env.cr.execute("""
                    SELECT postgis.st_asewkt(postgis.st_orientedenvelope(
                    """ + self._geom_field + """
                    )) FROM """ + self._gis_table + """
                    WHERE """ + self._link_field + """
                    ='""" + record.name + """'""")
                query_results = self.env.cr.dictfetchall()
                if (query_results and
                   query_results[0].get('st_asewkt') is not None):
                    oriented_envelope_ewkt = query_results[0].get('st_asewkt')
            record.oriented_envelope_ewkt = oriented_envelope_ewkt

    def _compute_area_gis(self):
        geom_ok = self._geom_ok()
        for record in self:
            area_gis = 0
            if geom_ok:
                self.env.cr.execute("""
                    SELECT postgis.geometrytype(""" + self._geom_field + """),
                    postgis.st_area(""" + self._geom_field + """)
                    FROM """ + self._gis_table + """
                    WHERE """ + self._link_field + """
                    ='""" + record.name + """'""")
                query_results = self.env.cr.dictfetchall()
                if (query_results and
                   query_results[0].get('geometrytype') is not None):
                    geometry_type = \
                        query_results[0].get('geometrytype').lower()
                    if (geometry_type == 'polygon' or
                       geometry_type == 'multipolygon'):
                        area_gis = \
                            round(float(query_results[0].get('st_area')))
            record.area_gis = area_gis

    def _compute_perimeter_gis(self):
        geom_ok = self._geom_ok()
        for record in self:
            perimeter_gis = 0
            if geom_ok:
                self.env.cr.execute("""
                    SELECT postgis.geometrytype(""" + self._geom_field + """),
                    postgis.st_perimeter(""" + self._geom_field + """)
                    FROM """ + self._gis_table + """
                    WHERE """ + self._link_field + """
                    ='""" + record.name + """'""")
                query_results = self.env.cr.dictfetchall()
                if (query_results and
                   query_results[0].get('geometrytype') is not None):
                    geometry_type = \
                        query_results[0].get('geometrytype').lower()
                    if (geometry_type == 'polygon' or
                       geometry_type == 'multipolygon'):
                        perimeter_gis = \
                            round(float(query_results[0].get('st_perimeter')))
            record.perimeter_gis = perimeter_gis

    def _compute_centroid_ewkt(self):
        geom_ok = self._geom_ok()
        for record in self:
            centroid_ewkt = ''
            if geom_ok:
                self.env.cr.execute("""
                    SELECT postgis.st_asewkt
                    (st_centroid(""" + self._geom_field + """))
                    FROM """ + self._gis_table + """
                    WHERE """ + self._link_field + """=
                    '""" + record.name + """'""")
                query_results = self.env.cr.dictfetchall()
                if (query_results and
                   query_results[0].get('st_asewkt') is not None):
                    centroid_ewkt = query_results[0].get('st_asewkt')
            record.centroid_ewkt = centroid_ewkt

    def _geom_ok(self):
        resp = (self._gis_table != '' and self._geom_field != '' and
                self._link_field != '')
        if resp:
            try:
                self.env.cr.execute(
                    'SELECT ' + self._link_field + ', ' + self._geom_field +
                    ' FROM ' + self._gis_table + ' LIMIT 1')
            except Exception:
                self.env.cr.rollback()
                resp = False
        return resp

    @api.model
    def extract_coordinates(self, geom_ewkt):
        srid = ''
        coordinates = ''
        if geom_ewkt:
            pos_semicolon = geom_ewkt.find(';')
            if pos_semicolon != -1 and pos_semicolon < len(geom_ewkt) - 1:
                coordinates = geom_ewkt[pos_semicolon + 1:]
                srid_temp = geom_ewkt[0:pos_semicolon]
                pos_equal = srid_temp.find('=')
                if pos_equal and pos_equal < len(srid_temp) - 1:
                    srid = srid_temp[pos_equal + 1:]
                if not srid:
                    coordinates = ''
        return srid, coordinates

    @api.model
    def extract_bounding_box(self, geom_ewkt):
        bounding_box = []
        srid, coordinates = self.extract_coordinates(geom_ewkt)
        if coordinates:
            coordinates = coordinates.lower()
            points = ''
            if coordinates.find('multipolygon') != -1:
                points = \
                    re.search(r'\(\(\((.*?)\)\)\)', coordinates).group(1)
            elif coordinates.find('polygon') != -1:
                points = \
                    re.search(r'\(\((.*?)\)\)', coordinates).group(1)
            if points:
                points = points.replace('),(', ', ').replace('), (', ', ')
                points = points.replace(', ', ',')
                list_of_points = points.split(',')
                first_point = True
                minx = 0
                maxx = 0
                miny = 0
                maxy = 0
                for point in list_of_points:
                    coordinates = point.split(' ')
                    if len(coordinates) == 2:
                        x = float(coordinates[0])
                        y = float(coordinates[1])
                        if first_point:
                            first_point = False
                            minx = x
                            maxx = x
                            miny = y
                            maxy = y
                        else:
                            if x < minx:
                                minx = x
                            if x > maxx:
                                maxx = x
                            if y < miny:
                                miny = y
                            if y > maxy:
                                maxy = y
                bounding_box = [minx, miny, maxx, maxy]
        return srid, bounding_box

    @api.model
    def get_bbox_final(self, zoom, bbox_initial,
                       image_width_initial, image_height_initial):
        bbox_final = [0, 0, 0, 0]
        image_width_final = 0
        image_height_final = 0
        if (bbox_initial and len(bbox_initial) == 4
           and image_width_initial >= 0 and image_height_initial >= 0):
            minx = bbox_initial[0]
            miny = bbox_initial[1]
            maxx = bbox_initial[2]
            maxy = bbox_initial[3]
            image_width_meters = maxx - minx
            image_height_meters = maxy - miny
            if (image_width_meters > 0 and image_height_meters > 0 and
               zoom >= 1):
                new_image_width_meters = \
                    image_width_meters * zoom
                new_image_height_meters = \
                    image_height_meters * zoom
                dif_width_meters = \
                    new_image_width_meters - image_width_meters
                dif_height_meters = \
                    new_image_height_meters - image_height_meters
                offset_width_meters = dif_width_meters / 2
                offset_height_meters = dif_height_meters / 2
                minx = int(round(minx - offset_width_meters))
                miny = int(round(miny - offset_height_meters))
                maxx = int(round(maxx + offset_width_meters))
                maxy = int(round(maxy + offset_height_meters))
                if image_width_initial == 0 and image_height_initial == 0:
                    image_height_initial = self.NORMAL_SIZE
                image_width_meters = maxx - minx
                image_height_meters = maxy - miny
                image_height_pixels = image_height_initial
                image_width_pixels = image_width_initial
                if image_width_pixels == 0 or image_height_pixels == 0:
                    if image_width_pixels == 0:
                        image_width_pixels = int(round((
                            image_width_meters * image_height_pixels) /
                            image_height_meters))
                    else:
                        image_height_pixels = int(round((
                            image_height_meters * image_width_pixels) /
                            image_width_meters))
                bbox_final = [minx, miny, maxx, maxy]
                image_width_final = image_width_pixels
                image_height_final = image_height_pixels
        return bbox_final, image_width_final, image_height_final

    def get_aerial_image(self,
                         wms='https://www.ign.es/wms-inspire/pnoa-ma',
                         layers='OI.OrthoimageCoverage',
                         styles='default',
                         image_width=0,
                         image_height=512,
                         format='png',
                         zoom=1.2,
                         get_raw=False,
                         filter=False):
        aerial_images = []
        # Number of layers passed
        number_of_layers = len(layers.split(',')) - 1
        for record in self:
            image = None
            srid, bounding_box = record.extract_bounding_box(
                record.geom_ewkt)
            if srid and bounding_box:
                bounding_box_final, image_width_pixels, image_height_pixels = \
                    self.get_bbox_final(zoom, bounding_box,
                                        image_width, image_height)
                if image_width_pixels > 0 and image_height_pixels > 0:
                    minx = bounding_box_final[0]
                    miny = bounding_box_final[1]
                    maxx = bounding_box_final[2]
                    maxy = bounding_box_final[3]
                    cql_filter = ''
                    if filter:
                        cql_filter = '&FILTER=' + '()' * number_of_layers + \
                            '(<Filter><PropertyIsLike wildCard="*" ' + \
                            'singleChar="." escape="!">' + \
                            '<PropertyName>' + self._link_field + \
                            '</PropertyName><Literal>' + record.name + \
                            '</Literal></PropertyIsLike></Filter>)'
                    url = wms + '?service=wms' + \
                        '&version=1.3.0&request=getmap&crs=epsg:' + str(srid) + \
                        '&bbox=' + str(minx) + ',' + str(miny) + ',' + \
                        str(maxx) + ',' + str(maxy) + \
                        '&width=' + str(image_width_pixels) + \
                        '&height=' + str(image_height_pixels) + \
                        '&layers=' + layers + \
                        '&styles=' + styles + \
                        cql_filter + \
                        '&format=image/' + format
                    request_ok = True
                    resp = None
                    try:
                        resp = requests.get(url, stream=True,
                                            timeout=self.OGC_TIMEOUT)
                    except Exception:
                        request_ok = False
                    if request_ok and resp.status_code == 200:
                        image_raw = io.BytesIO(resp.raw.read())
                        # When XML error returns a 200, but not image on raw
                        # Check before returning
                        try:
                            Image.open(image_raw)
                            image = base64.b64encode(image_raw.getvalue())
                        except Exception:
                            image = None
                        if image and get_raw:
                            image = image_raw
            aerial_images.append(image)
        if all(i is None for i in aerial_images):
            return None
        else:
            if len(aerial_images) == 1:
                aerial_images = aerial_images[0]
        return aerial_images
