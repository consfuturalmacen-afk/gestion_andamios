from odoo import fields, models


class AndamioObraStock(models.Model):
    _name = "andamio.obra.stock"
    _description = "Stock de Piezas por Obra"
    _order = "obra_id, pieza_id"

    obra_id = fields.Many2one("andamio.obra", string="Obra", required=True, ondelete="cascade")
    pieza_id = fields.Many2one("andamio.pieza", string="Pieza", required=True, ondelete="cascade")
    cantidad = fields.Float(string="Cantidad en Obra", default=0.0)
    stock_wh = fields.Float(
        string="Stock en WH/Stock",
        related="pieza_id.stock_total",
        readonly=True,
        store=True,
        group_operator="max",
    )

    _sql_constraints = [
        (
            "andamio_obra_stock_unique",
            "unique(obra_id, pieza_id)",
            "Ya existe un registro de stock para esta pieza en la obra.",
        )
    ]
