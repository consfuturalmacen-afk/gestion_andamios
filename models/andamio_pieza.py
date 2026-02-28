from odoo import fields, models


class AndamioPieza(models.Model):
    _name = "andamio.pieza"
    _description = "Pieza de Andamio"

    name = fields.Char(string="Nombre", required=True)
    codigo = fields.Char(string="Código", required=True, copy=False)
    image_1920 = fields.Image(string="Imagen")
    stock_total = fields.Float(string="Stock Total", default=0.0)

    _sql_constraints = [
        ("andamio_pieza_codigo_unique", "unique(codigo)", "El código debe ser único."),
    ]
