from odoo import fields, models


class AndamioObra(models.Model):
    _name = "andamio.obra"
    _description = "Obra"

    name = fields.Char(string="Nombre de la Obra", required=True)
    ubicacion_id = fields.Many2one(
        "stock.location",
        string="Ubicación Interna",
        domain=[("usage", "=", "internal")],
        required=True,
    )
    cliente = fields.Char(string="Cliente")
    encargado_id = fields.Many2one("hr.employee", string="Encargado")
