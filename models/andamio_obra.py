from odoo import fields, models


class AndamioObra(models.Model):
    _name = "andamio.obra"
    _description = "Obra"

    name = fields.Char(string="Nombre de la Obra", required=True)
    ubicacion = fields.Char(string="Ubicación")
    cliente = fields.Char(string="Cliente")
    encargado_id = fields.Many2one("res.users", string="Encargado")
